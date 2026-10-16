"""Seuils d'alerte du pipeline.

Source unique de vérité : le DAG (tâche enregistrer_metriques) et le dashboard Streamlit
lisent tous les deux ces valeurs. Modifier un seuil ici le change partout.
Justification de chaque seuil : docs/04_plan_monitoring.md.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

SEUILS = {
    # Précision : part des publications extraites qui sortent valides de la transformation.
    "taux_valides_min": 0.90,
    # Précision : part des publications valides dont l'image est réellement accessible.
    "taux_images_valides_min": 0.80,
    # Volume : un run normal extrait ~95-100 publications (50 NewsAPI + ~48 RSS).
    "nb_extraits_min": 50,
    # Rapidité : un run normal dure ~30 s ; 5 min signale un blocage (site lent, timeouts).
    "duree_totale_max_s": 300,
    # Coût : quota du plan gratuit NewsAPI = 100 requêtes/jour ; on alerte avant de l'atteindre.
    "appels_newsapi_jour_max": 80,
}

TABLE_EXECUTIONS = "executions"
