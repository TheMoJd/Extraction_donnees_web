"""Extraction des publications via l'API NewsAPI (endpoint /v2/everything)."""
from typing import Any

import requests

from extraction.config import NEWSAPI_KEY, NEWSAPI_ENDPOINT, NEWSAPI_PARAMS
from extraction.common import setup_logger, looks_like_image_url, now_iso

logger = setup_logger("extraction.newsapi")


def fetch_articles() -> list[dict[str, Any]]:
    """Connexion : appelle l'API NewsAPI et retourne les articles bruts (liste vide si échec)."""
    if not NEWSAPI_KEY:
        logger.error("NEWSAPI_KEY manquante : renseigne-la dans le fichier .env")
        return []

    params = {**NEWSAPI_PARAMS, "apiKey": NEWSAPI_KEY}

    try:
        response = requests.get(NEWSAPI_ENDPOINT, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.error("Échec de l'appel NewsAPI : %s", exc)
        return []

    payload = response.json()
    if payload.get("status") != "ok":
        logger.error("Réponse NewsAPI en erreur : %s", payload.get("message"))
        return []

    articles = payload.get("articles", [])
    logger.info("NewsAPI : %d articles récupérés", len(articles))
    return articles


def parse_articles(raw_articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parsing : normalise les articles NewsAPI vers le schéma commun du pipeline."""
    records = []
    for article in raw_articles:
        image_url = article.get("urlToImage")
        records.append({
            "title": article.get("title"),
            "content": article.get("description") or article.get("content"),
            "image_url": image_url,
            "has_valid_image": looks_like_image_url(image_url),
            "published_at": article.get("publishedAt"),
            "source_domain": (article.get("source") or {}).get("name"),
            "url": article.get("url"),
            "source_type": "newsapi",
            "extracted_at": now_iso(),
        })
    return records


def extract() -> list[dict[str, Any]]:
    """Point d'entrée du module : connexion + parsing pour la source NewsAPI."""
    raw = fetch_articles()
    return parse_articles(raw)
