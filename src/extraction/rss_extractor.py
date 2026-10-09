"""Extraction des publications via des flux RSS de presse."""
from typing import Any

import feedparser

from extraction.config import RSS_FEEDS
from extraction.common import setup_logger, looks_like_image_url, now_iso

logger = setup_logger("extraction.rss")


def _extract_image_from_entry(entry: dict[str, Any]) -> str | None:
    """Cherche une image dans les champs RSS usuels (media_content, enclosure)."""
    media_content = entry.get("media_content")
    if media_content:
        return media_content[0].get("url")

    for link in entry.get("links", []):
        if link.get("type", "").startswith("image/"):
            return link.get("href")

    return None


def fetch_feed(feed_name: str, feed_url: str) -> list[dict[str, Any]]:
    """Connexion : lit un flux RSS et retourne ses entrées brutes (liste vide si échec)."""
    try:
        parsed = feedparser.parse(feed_url)
    except Exception as exc:  # feedparser peut lever divers types d'erreurs réseau/parsing
        logger.error("Échec de lecture du flux %s (%s) : %s", feed_name, feed_url, exc)
        return []

    if parsed.bozo and not parsed.entries:
        logger.error("Flux RSS invalide ou inaccessible : %s (%s)", feed_name, feed_url)
        return []

    logger.info("Flux %s : %d entrées récupérées", feed_name, len(parsed.entries))
    return parsed.entries


def parse_entries(feed_name: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parsing : normalise les entrées RSS vers le schéma commun du pipeline."""
    records = []
    for entry in entries:
        image_url = _extract_image_from_entry(entry)
        records.append({
            "title": entry.get("title"),
            "content": entry.get("summary"),
            "image_url": image_url,
            "has_valid_image": looks_like_image_url(image_url),
            "published_at": entry.get("published"),
            "source_domain": feed_name,
            "url": entry.get("link"),
            "source_type": "rss",
            "extracted_at": now_iso(),
        })
    return records


def extract() -> list[dict[str, Any]]:
    """Point d'entrée du module : connexion + parsing pour tous les flux RSS configurés."""
    all_records = []
    for feed_name, feed_url in RSS_FEEDS.items():
        entries = fetch_feed(feed_name, feed_url)
        all_records.extend(parse_entries(feed_name, entries))
    return all_records
