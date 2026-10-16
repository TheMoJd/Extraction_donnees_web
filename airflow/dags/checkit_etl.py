"""DAG ETL CheckIt.AI : extraction (NewsAPI + RSS) -> transformation -> chargement PostgreSQL,
puis enregistrement des métriques du run (monitoring).

Chaque tâche appelle les fonctions des packages du projet (src/, monté dans /opt/checkit/src)
et transmet son rapport (chemin du fichier produit + compteurs) à la suivante via XCom.
"""
from datetime import datetime, timedelta, timezone

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG, TriggerRule

# Les imports du projet sont faits dans les fonctions, pas en haut du fichier :
# le dag-processor relit ce fichier toutes les ~30 s, et importer le projet à chaque
# lecture créerait des dossiers, ouvrirait des fichiers de log, etc. pour rien.

ETAPES = ("extraire", "transformer", "charger")


def _mesure(fonction, *args) -> dict:
    """Exécute une étape et ajoute à son rapport sa durée et la mémoire maximale du processus."""
    import resource
    import time

    debut = time.perf_counter()
    rapport = fonction(*args)
    rapport["duree_s"] = round(time.perf_counter() - debut, 2)
    rapport["memoire_max_mo"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    return rapport


def _connexion_checkit():
    """Connexion psycopg2 à la base checkit, identifiants lus depuis la Connection Airflow.

    Les identifiants viennent de la Connection (mot de passe chiffré par Fernet), pas d'une
    variable d'environnement visible par toutes les tâches.
    On n'utilise pas PostgresHook.get_conn() : en Airflow 3.3 il renvoie une connexion
    psycopg 3, incompatible avec execute_values de psycopg2 utilisé par le module chargement.
    """
    import psycopg2
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    conn = PostgresHook.get_connection("checkit_postgres")
    return psycopg2.connect(
        host=conn.host, port=conn.port, dbname=conn.schema,
        user=conn.login, password=conn.password,
    )


def extraire() -> dict:
    from extraction import main as extraction

    return _mesure(extraction.run)


def transformer(ti) -> dict:
    from pathlib import Path

    from transformation import main as transformation

    chemin_brut = ti.xcom_pull(task_ids="extraire")["chemin"]
    return _mesure(transformation.run, Path(chemin_brut))


def charger(ti) -> dict:
    from pathlib import Path

    from chargement import main as chargement

    chemin_csv = ti.xcom_pull(task_ids="transformer")["chemin"]
    connexion = _connexion_checkit()
    try:
        return _mesure(chargement.charge_fichier, Path(chemin_csv), connexion)
    finally:
        connexion.close()


def enregistrer_metriques(ti, dag_run) -> None:
    """Assemble les rapports des 3 étapes en une ligne de la table executions.

    S'exécute même si une étape a échoué (trigger_rule ALL_DONE) : un run en échec doit
    aussi apparaître dans le dashboard. Dans ce cas, la tâche échoue ensuite volontairement
    pour que le run reste marqué en échec dans Airflow.
    """
    import os

    from airflow.sdk.exceptions import AirflowFailException

    from monitoring import main as monitoring

    rapports = {etape: ti.xcom_pull(task_ids=etape) for etape in ETAPES}
    print("Rapports reçus :", ", ".join(f"{e}={'ok' if r else 'absent'}" for e, r in rapports.items()))
    extr, transf, charg = (rapports[e] or {} for e in ETAPES)
    etape_en_echec = next((e for e in ETAPES if rapports[e] is None), None)

    tailles = [os.path.getsize(r["chemin"]) for r in (extr, transf) if r.get("chemin") and os.path.exists(r["chemin"])]
    memoires = [r["memoire_max_mo"] for r in (extr, transf, charg) if "memoire_max_mo" in r]

    execution = {
        "run_id": dag_run.run_id,
        "debut": dag_run.start_date,
        "fin": datetime.now(timezone.utc),
        "statut": "echec" if etape_en_echec else "succes",
        "etape_en_echec": etape_en_echec,
        "nb_newsapi": extr.get("nb_newsapi"),
        "nb_rss": extr.get("nb_rss"),
        "nb_extraits": transf.get("nb_lus"),
        "nb_valides": transf.get("nb_valides"),
        "nb_rejetes": transf.get("nb_rejetes"),
        "nb_doublons": transf.get("nb_doublons"),
        "nb_images_valides": transf.get("nb_images_valides"),
        "nb_nouvelles": charg.get("nb_nouvelles"),
        "nb_deja_presentes": charg.get("nb_deja_presentes"),
        "duree_extraction_s": extr.get("duree_s"),
        "duree_transformation_s": transf.get("duree_s"),
        "duree_chargement_s": charg.get("duree_s"),
        "memoire_max_mo": max(memoires) if memoires else None,
        "taille_fichiers_ko": round(sum(tailles) / 1024, 1) if tailles else None,
        "appels_newsapi": extr.get("appels_newsapi"),
    }

    connexion = _connexion_checkit()
    try:
        monitoring.enregistre_execution(connexion, execution)
    finally:
        connexion.close()

    if etape_en_echec:
        raise AirflowFailException(f"Run en échec à l'étape « {etape_en_echec} » (métriques enregistrées)")


def alerte_echec_tache(context) -> None:
    """Callback appelé par Airflow quand une tâche échoue définitivement (après ses retries).

    En local, l'alerte est écrite dans logs/monitoring.log. En production, c'est ici qu'on
    brancherait l'envoi d'un e-mail ou d'un message Slack (cf. docs/04_plan_monitoring.md).
    """
    from monitoring.main import setup_logger

    ti = context["ti"]
    setup_logger("monitoring.alertes").error(
        "[%s] CRITIQUE : la tâche « %s » a échoué définitivement (tentative n°%s). "
        "Erreur complète dans les logs de la tâche (UI Airflow).",
        ti.run_id, ti.task_id, ti.try_number,
    )


with DAG(
    dag_id="checkit_etl",
    description="Extraction multimodale (texte + image), transformation, chargement PostgreSQL et métriques",
    schedule="0 6 * * *",  # tous les jours à 6h UTC : 1 appel NewsAPI/jour sur un quota de 100
    start_date=datetime(2026, 10, 1),
    catchup=False,  # pas de rattrapage des jours passés : NewsAPI ne renvoie que l'actualité du moment
    # Un seul run à la fois : les fichiers sont horodatés à la seconde, deux runs simultanés
    # écriraient dans le même fichier (constaté lors du premier test).
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=30),  # un run normal dure ~30 s
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=10),  # une tâche bloquée est tuée puis retentée
        "on_failure_callback": alerte_echec_tache,
    },
    tags=["checkit", "etl"],
) as dag:
    tache_extraire = PythonOperator(task_id="extraire", python_callable=extraire)
    tache_transformer = PythonOperator(task_id="transformer", python_callable=transformer)
    tache_charger = PythonOperator(task_id="charger", python_callable=charger)
    tache_metriques = PythonOperator(
        task_id="enregistrer_metriques",
        python_callable=enregistrer_metriques,
        trigger_rule=TriggerRule.ALL_DONE,  # tourne aussi quand une étape a échoué
        retries=0,
    )

    tache_extraire >> tache_transformer >> tache_charger >> tache_metriques
