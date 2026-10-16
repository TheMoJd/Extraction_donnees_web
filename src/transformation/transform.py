"""Fonctions de nettoyage, normalisation et validation appliquées à chaque publication."""
import hashlib
import html
import re
from datetime import timezone
from urllib.parse import urlparse

import requests
from dateutil import parser as date_parser

from transformation.config import IMAGE_VALIDATION_TIMEOUT
from transformation.common import setup_logger

logger = setup_logger("transformation.transform")

_TAG_RE = re.compile(r"<[^>]+>")
_NEWSAPI_TRUNCATION_RE = re.compile(r"\s*\[\+\d+ chars\]\s*$")


def nettoie_texte(texte: str | None) -> str:
    """Supprime le HTML, les entités, la troncature NewsAPI, et normalise les espaces.

    Nécessaire car les résumés RSS embarquent parfois du HTML brut, et NewsAPI
    tronque le champ `content` avec un suffixe "[+1234 chars]" en plan gratuit.
    """
    if not texte:
        return ""
    texte = html.unescape(texte)
    texte = _TAG_RE.sub(" ", texte)
    texte = _NEWSAPI_TRUNCATION_RE.sub("", texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte


def normalise_date(date_brute: str | None) -> str | None:
    """Convertit une date NewsAPI (ISO 8601) ou RSS (RFC 822) vers un format ISO 8601 UTC unique."""
    if not date_brute:
        return None
    try:
        dt = date_parser.parse(date_brute)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError) as exc:
        logger.warning("Date illisible ignorée (%s) : %s", date_brute, exc)
        return None


def valide_image(url: str | None) -> bool:
    """Vérifie que l'URL pointe réellement vers une image accessible (requête HEAD).

    Contrôle plus strict que la simple vérification de format faite à l'extraction :
    ici on interroge réellement le serveur distant.
    """
    if not url:
        return False
    try:
        response = requests.head(url, timeout=IMAGE_VALIDATION_TIMEOUT, allow_redirects=True)
        content_type = response.headers.get("Content-Type", "")
        return response.status_code == 200 and content_type.startswith("image/")
    except requests.exceptions.RequestException as exc:
        logger.warning("Image inaccessible (%s) : %s", url, exc)
        return False


def extrait_domaine(url: str | None) -> str | None:
    """Extrait le nom de domaine d'une URL, utile comme indice de fiabilité de la source."""
    if not url:
        return None
    return urlparse(url).netloc or None


def genere_id(url: str) -> str:
    """Identifiant stable (hash de l'URL) pour dédupliquer les publications entre sources."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
