"""Paramètres configurables du pipeline de transformation."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
LOG_DIR = BASE_DIR / "logs"

PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Délai max (secondes) pour vérifier qu'une image est réellement accessible.
IMAGE_VALIDATION_TIMEOUT = 5

# Longueur minimale du titre pour qu'une publication soit jugée exploitable.
MIN_TITLE_LENGTH = 5
