"""Script principal d'extraction : orchestre NewsAPI + RSS et sauvegarde le résultat.

Exécution (depuis src/) : python -m extraction.main
Aucune intervention manuelle requise une fois NEWSAPI_KEY renseignée dans .env.
"""
from datetime import datetime, timezone
from pathlib import Path

from extraction.config import RAW_DATA_DIR
from extraction.common import setup_logger, save_records_to_json
from extraction import newsapi_extractor
from extraction import rss_extractor

logger = setup_logger("extraction.main")


def run() -> Path:
    logger.info("Démarrage de l'extraction")

    records = []
    records.extend(newsapi_extractor.extract())
    records.extend(rss_extractor.extract())

    valid_records = [r for r in records if r.get("title") and r.get("url")]
    dropped = len(records) - len(valid_records)
    if dropped:
        logger.warning("%d enregistrement(s) ignoré(s) (titre ou url manquant)", dropped)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = RAW_DATA_DIR / f"extraction_{timestamp}.json"
    save_records_to_json(valid_records, output_path)

    logger.info(
        "Extraction terminée : %d publication(s) sauvegardée(s) dans %s",
        len(valid_records),
        output_path,
    )
    return output_path


if __name__ == "__main__":
    run()
