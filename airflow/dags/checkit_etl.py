"""DAG ETL CheckIt.AI : extraction (NewsAPI + RSS) -> transformation -> chargement PostgreSQL.

Chaque tâche appelle les fonctions des packages du projet (src/, monté dans /opt/checkit/src)
et transmet le chemin du fichier produit à la suivante via XCom.
"""
from datetime import datetime, timedelta

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

# Les imports du projet sont faits dans les fonctions, pas en haut du fichier :
# le dag-processor relit ce fichier toutes les ~30 s, et importer le projet à chaque
# lecture créerait des dossiers, ouvrirait des fichiers de log, etc. pour rien.


def extraire() -> str:
    from extraction import main as extraction

    return str(extraction.run())


def transformer(ti) -> str:
    from pathlib import Path

    from transformation import main as transformation

    chemin_brut = ti.xcom_pull(task_ids="extraire")
    return str(transformation.run(Path(chemin_brut)))


def charger(ti) -> int:
    from pathlib import Path

    import psycopg2
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    from chargement import main as chargement

    chemin_csv = ti.xcom_pull(task_ids="transformer")
    # Les identifiants viennent de la Connection Airflow (mot de passe chiffré par Fernet),
    # pas d'une variable d'environnement visible par toutes les tâches.
    # On n'utilise pas PostgresHook.get_conn() : en Airflow 3.3 il renvoie une connexion
    # psycopg 3, incompatible avec execute_values de psycopg2 utilisé par le module chargement.
    conn = PostgresHook.get_connection("checkit_postgres")
    connexion = psycopg2.connect(
        host=conn.host, port=conn.port, dbname=conn.schema,
        user=conn.login, password=conn.password,
    )
    try:
        return chargement.charge_fichier(Path(chemin_csv), connexion)
    finally:
        connexion.close()


with DAG(
    dag_id="checkit_etl",
    description="Extraction multimodale (texte + image), transformation et chargement PostgreSQL",
    schedule="0 6 * * *",  # tous les jours à 6h UTC : 1 appel NewsAPI/jour sur un quota de 100
    start_date=datetime(2026, 10, 1),
    catchup=False,  # pas de rattrapage des jours passés : NewsAPI ne renvoie que l'actualité du moment
    # Un seul run à la fois : les fichiers sont horodatés à la seconde, deux runs simultanés
    # écriraient dans le même fichier (constaté lors du premier test).
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["checkit", "etl"],
) as dag:
    tache_extraire = PythonOperator(task_id="extraire", python_callable=extraire)
    tache_transformer = PythonOperator(task_id="transformer", python_callable=transformer)
    tache_charger = PythonOperator(task_id="charger", python_callable=charger)

    tache_extraire >> tache_transformer >> tache_charger
