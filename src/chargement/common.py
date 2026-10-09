"""Fonctions partagées par le module de chargement."""
import logging

from chargement.config import LOG_DIR


def setup_logger(name: str) -> logging.Logger:
    """Configure un logger écrivant à la fois en console et dans logs/chargement.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / "chargement.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
