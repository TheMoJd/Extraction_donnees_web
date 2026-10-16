"""Évaluation des KPI d'un run et enregistrement dans la table executions."""
import logging

from monitoring.config import LOG_DIR, SEUILS, TABLE_EXECUTIONS

CRITIQUE = "CRITIQUE"
ATTENTION = "ATTENTION"


def setup_logger(name: str) -> logging.Logger:
    """Configure un logger écrivant à la fois en console et dans logs/monitoring.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / "monitoring.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger("monitoring.main")


def ratio(numerateur: int | None, denominateur: int | None) -> float | None:
    if not denominateur or numerateur is None:
        return None
    return numerateur / denominateur


def evalue_alertes(execution: dict, appels_newsapi_jour: int) -> list[str]:
    """Compare les métriques d'un run aux seuils et retourne les alertes, préfixées par leur niveau."""
    alertes = []

    if execution["statut"] == "echec":
        alertes.append(f"{CRITIQUE} : échec de l'étape « {execution['etape_en_echec']} »")
        return alertes  # métriques partielles : les autres contrôles n'ont pas de sens

    if execution["nb_newsapi"] == 0:
        alertes.append(f"{CRITIQUE} : NewsAPI n'a renvoyé aucun article (clé, quota ou panne)")
    if execution["nb_rss"] == 0:
        alertes.append(f"{CRITIQUE} : les flux RSS n'ont renvoyé aucune entrée")

    if execution["nb_extraits"] < SEUILS["nb_extraits_min"]:
        alertes.append(
            f"{ATTENTION} : volume faible, {execution['nb_extraits']} publications "
            f"(seuil {SEUILS['nb_extraits_min']})"
        )

    taux_valides = ratio(execution["nb_valides"], execution["nb_extraits"])
    if taux_valides is not None and taux_valides < SEUILS["taux_valides_min"]:
        alertes.append(
            f"{ATTENTION} : {taux_valides:.0%} de données valides "
            f"(seuil {SEUILS['taux_valides_min']:.0%})"
        )

    taux_images = ratio(execution["nb_images_valides"], execution["nb_valides"])
    if taux_images is not None and taux_images < SEUILS["taux_images_valides_min"]:
        alertes.append(
            f"{ATTENTION} : {taux_images:.0%} d'images accessibles "
            f"(seuil {SEUILS['taux_images_valides_min']:.0%})"
        )

    duree = sum(execution[c] or 0 for c in ("duree_extraction_s", "duree_transformation_s", "duree_chargement_s"))
    if duree > SEUILS["duree_totale_max_s"]:
        alertes.append(
            f"{ATTENTION} : run lent, {duree:.0f} s (seuil {SEUILS['duree_totale_max_s']} s)"
        )

    if appels_newsapi_jour > SEUILS["appels_newsapi_jour_max"]:
        alertes.append(
            f"{ATTENTION} : {appels_newsapi_jour} appels NewsAPI aujourd'hui "
            f"(seuil {SEUILS['appels_newsapi_jour_max']}, quota 100)"
        )

    return alertes


def compte_appels_newsapi_du_jour(connexion, run_id: str) -> int:
    """Appels NewsAPI déjà enregistrés aujourd'hui (UTC), hors run en cours."""
    with connexion.cursor() as curseur:
        curseur.execute(
            f"SELECT COALESCE(SUM(appels_newsapi), 0) FROM {TABLE_EXECUTIONS} "
            "WHERE debut >= date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' "
            "AND run_id <> %s",
            (run_id,),
        )
        return int(curseur.fetchone()[0])


def enregistre_execution(connexion, execution: dict) -> list[str]:
    """Calcule les alertes, journalise, puis insère (ou met à jour) la ligne du run.

    Retourne la liste des alertes pour que l'appelant puisse réagir.
    """
    appels_jour = compte_appels_newsapi_du_jour(connexion, execution["run_id"]) + (execution.get("appels_newsapi") or 0)
    alertes = evalue_alertes(execution, appels_jour)
    execution = {**execution, "alertes": alertes}

    for alerte in alertes:
        if alerte.startswith(CRITIQUE):
            logger.error("[%s] %s", execution["run_id"], alerte)
        else:
            logger.warning("[%s] %s", execution["run_id"], alerte)
    if not alertes:
        logger.info("[%s] Run conforme : aucune alerte", execution["run_id"])

    colonnes = list(execution)
    mises_a_jour = ", ".join(f"{c} = EXCLUDED.{c}" for c in colonnes if c != "run_id")
    requete = (
        f"INSERT INTO {TABLE_EXECUTIONS} ({', '.join(colonnes)}) "
        f"VALUES ({', '.join(['%s'] * len(colonnes))}) "
        f"ON CONFLICT (run_id) DO UPDATE SET {mises_a_jour}"
    )
    with connexion.cursor() as curseur:
        curseur.execute(requete, [execution[c] for c in colonnes])
    connexion.commit()
    return alertes
