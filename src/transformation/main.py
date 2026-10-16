"""Pipeline de transformation : lecture -> traitement -> export.

Exécution (depuis src/) : python -m transformation.main [chemin_fichier_brut.json]
Sans argument, traite le fichier le plus récent de data/raw/.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from transformation.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, MIN_TITLE_LENGTH
from transformation.common import setup_logger
from transformation import transform

logger = setup_logger("transformation.main")


def lire_fichier_brut(chemin: Path) -> list[dict]:
    """Étape 1/3 : lecture du fichier JSON brut produit par l'extraction."""
    with open(chemin, encoding="utf-8") as f:
        records = json.load(f)
    logger.info("Lecture de %s : %d enregistrement(s)", chemin.name, len(records))
    return records


def trouve_dernier_fichier_brut() -> Path | None:
    fichiers = sorted(RAW_DATA_DIR.glob("extraction_*.json"))
    return fichiers[-1] if fichiers else None


def traite_enregistrement(record: dict) -> dict | None:
    """Étape 2/3 : nettoyage, normalisation et validation d'une publication.

    Retourne None si la publication n'est pas exploitable (titre trop court, url absente).
    """
    titre = transform.nettoie_texte(record.get("title"))
    if len(titre) < MIN_TITLE_LENGTH:
        return None

    url = record.get("url")
    if not url:
        return None

    contenu = transform.nettoie_texte(record.get("content"))
    image_url = record.get("image_url")

    return {
        "id": transform.genere_id(url),
        "titre": titre,
        "contenu": contenu,
        "longueur_contenu": len(contenu),
        "image_url": image_url,
        "image_valide": transform.valide_image(image_url),
        "date_publication": transform.normalise_date(record.get("published_at")),
        "domaine_source": transform.extrait_domaine(url) or record.get("source_domain"),
        "url": url,
        "source_type": record.get("source_type"),
        "transforme_at": datetime.now(timezone.utc).isoformat(),
    }


def deduplique(records: list[dict]) -> list[dict]:
    """Supprime les doublons (même id = même URL), au cas où deux sources se recoupent."""
    vus = set()
    uniques = []
    for r in records:
        if r["id"] in vus:
            continue
        vus.add(r["id"])
        uniques.append(r)
    return uniques


def exporte_csv(records: list[dict], chemin: Path) -> None:
    """Étape 3/3 : export du jeu de données nettoyé au format CSV."""
    import pandas as pd

    chemin.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(chemin, index=False, encoding="utf-8")


def run(chemin_brut: Path | None = None) -> dict:
    """Transforme un fichier brut et retourne un rapport (chemin du CSV + compteurs pour le monitoring)."""
    chemin_brut = chemin_brut or trouve_dernier_fichier_brut()
    if chemin_brut is None:
        logger.error("Aucun fichier brut trouvé dans %s", RAW_DATA_DIR)
        raise FileNotFoundError(f"Aucun fichier brut dans {RAW_DATA_DIR}")

    records_bruts = lire_fichier_brut(chemin_brut)

    records_traites = [traite_enregistrement(r) for r in records_bruts]
    records_valides = [r for r in records_traites if r is not None]
    rejetes = len(records_bruts) - len(records_valides)

    records_uniques = deduplique(records_valides)
    doublons = len(records_valides) - len(records_uniques)

    images_valides = sum(1 for r in records_uniques if r["image_valide"])

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    chemin_sortie = PROCESSED_DATA_DIR / f"processed_{timestamp}.csv"
    exporte_csv(records_uniques, chemin_sortie)

    logger.info(
        "Transformation terminée : %d valides / %d rejetés / %d doublons / %d images valides -> %s",
        len(records_uniques), rejetes, doublons, images_valides, chemin_sortie,
    )
    return {
        "chemin": str(chemin_sortie),
        "nb_lus": len(records_bruts),
        "nb_valides": len(records_uniques),
        "nb_rejetes": rejetes,
        "nb_doublons": doublons,
        "nb_images_valides": images_valides,
    }


if __name__ == "__main__":
    arg_chemin = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run(arg_chemin)
