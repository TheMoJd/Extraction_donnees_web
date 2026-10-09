"""Chargement : CSV transformé -> table publications de PostgreSQL.

Exécution locale (depuis src/) : python -m chargement.main [chemin_fichier.csv]
Sans argument, charge le CSV le plus récent de data/processed/.
Nécessite le PostgreSQL du docker-compose démarré et CHECKIT_ETL_PASSWORD dans .env.
"""
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from chargement.config import COLONNES, DB_PARAMS, PROCESSED_DATA_DIR, TABLE_PUBLICATIONS
from chargement.common import setup_logger

logger = setup_logger("chargement.main")


def trouve_dernier_csv() -> Path | None:
    fichiers = sorted(PROCESSED_DATA_DIR.glob("processed_*.csv"))
    return fichiers[-1] if fichiers else None


def lit_csv(chemin: Path) -> list[tuple]:
    """Lit le CSV transformé et le convertit en lignes prêtes pour l'INSERT.

    Les cellules vides deviennent None (NULL en SQL) au lieu de NaN, que PostgreSQL refuserait.
    """
    df = pd.read_csv(chemin, encoding="utf-8")[COLONNES]
    df = df.astype(object).where(df.notna(), None)
    lignes = [tuple(ligne) for ligne in df.itertuples(index=False)]
    logger.info("Lecture de %s : %d publication(s)", chemin.name, len(lignes))
    return lignes


def insere_publications(connexion, lignes: list[tuple]) -> int:
    """Insère les publications et retourne le nombre de nouvelles lignes.

    ON CONFLICT DO NOTHING rend le chargement idempotent : relancer la tâche, ou recharger
    un article déjà vu la veille, n'ajoute pas de doublon et ne provoque pas d'erreur.
    """
    if not lignes:
        return 0

    requete = (
        f"INSERT INTO {TABLE_PUBLICATIONS} ({', '.join(COLONNES)}) VALUES %s "
        "ON CONFLICT (id) DO NOTHING RETURNING id"
    )
    with connexion.cursor() as curseur:
        inseres = execute_values(curseur, requete, lignes, fetch=True)
    connexion.commit()
    return len(inseres)


def charge_fichier(chemin: Path, connexion) -> int:
    """Point d'entrée réutilisé par le DAG Airflow, qui fournit sa propre connexion."""
    lignes = lit_csv(chemin)
    try:
        nouvelles = insere_publications(connexion, lignes)
    except psycopg2.Error as exc:
        connexion.rollback()
        logger.error("Échec du chargement de %s : %s", chemin.name, exc)
        raise

    logger.info(
        "Chargement terminé : %d nouvelle(s) publication(s) / %d déjà présente(s)",
        nouvelles, len(lignes) - nouvelles,
    )
    return nouvelles


def run(chemin_csv: Path | None = None) -> int:
    """Exécution hors Airflow : se connecte avec les paramètres de config.py."""
    chemin_csv = chemin_csv or trouve_dernier_csv()
    if chemin_csv is None:
        logger.error("Aucun fichier transformé trouvé dans %s", PROCESSED_DATA_DIR)
        raise FileNotFoundError(f"Aucun fichier transformé dans {PROCESSED_DATA_DIR}")

    if not DB_PARAMS["password"]:
        logger.error("CHECKIT_ETL_PASSWORD manquant : renseigne-le dans le fichier .env")
        raise RuntimeError("CHECKIT_ETL_PASSWORD manquant")

    connexion = psycopg2.connect(**DB_PARAMS)
    try:
        return charge_fichier(chemin_csv, connexion)
    finally:
        connexion.close()


if __name__ == "__main__":
    arg_chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run(arg_chemin)
