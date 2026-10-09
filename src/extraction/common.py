"""Fonctions partagées par les extracteurs : logging, validation, sauvegarde."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from extraction.config import LOG_DIR

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def setup_logger(name: str) -> logging.Logger:
    """Configure un logger écrivant à la fois en console et dans logs/extraction.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # évite les doublons de handlers si appelé plusieurs fois

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / "extraction.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def looks_like_image_url(url: str | None) -> bool:
    """Vérification légère (format) qu'une URL pointe vraisemblablement vers une image.

    La vérification d'accessibilité réelle (requête HEAD) est faite à l'étape
    de transformation pour ne pas ralentir l'extraction avec des appels réseau supplémentaires.
    """
    if not url:
        return False
    return url.lower().split("?")[0].endswith(IMAGE_EXTENSIONS)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_records_to_json(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
