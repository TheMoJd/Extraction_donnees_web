"""Paramètres configurables du module de chargement.

Les identifiants de la base ne servent qu'aux exécutions hors Airflow (en local).
Dans Airflow, la connexion vient de la Connection "checkit_postgres", chiffrée par Fernet.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
LOG_DIR = BASE_DIR / "logs"

load_dotenv(BASE_DIR / ".env")

LOG_DIR.mkdir(parents=True, exist_ok=True)

TABLE_PUBLICATIONS = "publications"

# Ordre des colonnes du CSV produit par le pipeline, et donc de l'INSERT.
COLONNES = [
    "id", "titre", "contenu", "longueur_contenu", "image_url", "image_valide",
    "date_publication", "domaine_source", "url", "source_type", "transforme_at",
]

# --- Connexion locale (hors Airflow) : PostgreSQL du docker-compose, exposé sur 5435 ---
DB_PARAMS = {
    "host": os.getenv("CHECKIT_DB_HOST", "localhost"),
    "port": int(os.getenv("CHECKIT_DB_PORT", "5435")),
    "dbname": os.getenv("CHECKIT_DB_NAME", "checkit"),
    "user": os.getenv("CHECKIT_DB_USER", "checkit_etl"),
    "password": os.getenv("CHECKIT_ETL_PASSWORD", ""),
}
