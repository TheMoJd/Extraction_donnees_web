"""Paramètres configurables du module d'extraction.

Toute valeur sensible (clé API) vient du fichier .env à la racine du projet,
jamais codée en dur ici.
"""
from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
LOG_DIR = BASE_DIR / "logs"

load_dotenv(BASE_DIR / ".env")

RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- NewsAPI ---
# NB : l'endpoint /v2/top-headlines avec country="fr" renvoie 0 résultat sur le plan
# gratuit (limitation constatée de NewsAPI, top-headlines y est de facto restreint
# à quelques pays). On utilise donc /v2/everything avec une recherche par mots-clés,
# ce qui est aussi plus pertinent pour cibler des sujets d'actualité précis.
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_ENDPOINT = "https://newsapi.org/v2/everything"
NEWSAPI_QUERY = "France"
NEWSAPI_PARAMS = {
    "q": NEWSAPI_QUERY,
    "language": "fr",
    "sortBy": "publishedAt",
    "pageSize": 50,
}

# --- Flux RSS (nom -> URL) ---
RSS_FEEDS = {
    "Le Monde": "https://www.lemonde.fr/rss/une.xml",
    "France Info": "https://www.francetvinfo.fr/titres.rss",
}
