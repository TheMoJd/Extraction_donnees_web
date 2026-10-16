"""Tests des règles d'alerte du monitoring (fonction pure : ni base, ni réseau).

Exécution (depuis la racine) : .venv/Scripts/python -m pytest
"""
from monitoring.config import SEUILS
from monitoring.main import ATTENTION, CRITIQUE, evalue_alertes


def run_normal(**modifs) -> dict:
    """Un run conforme, inspiré d'un run réel ; chaque test modifie un seul champ."""
    execution = {
        "statut": "succes", "etape_en_echec": None,
        "nb_newsapi": 50, "nb_rss": 47, "nb_extraits": 97,
        "nb_valides": 97, "nb_images_valides": 95,
        "duree_extraction_s": 1.4, "duree_transformation_s": 24.6, "duree_chargement_s": 0.1,
    }
    return {**execution, **modifs}


def test_run_normal_sans_alerte():
    assert evalue_alertes(run_normal(), appels_newsapi_jour=1) == []


def test_echec_donne_une_seule_alerte_critique():
    alertes = evalue_alertes(run_normal(statut="echec", etape_en_echec="charger"), appels_newsapi_jour=1)
    assert alertes == [f"{CRITIQUE} : échec de l'étape « charger »"]


def test_source_vide_est_critique():
    alertes = evalue_alertes(run_normal(nb_newsapi=0, nb_extraits=47, nb_valides=47, nb_images_valides=47), 1)
    assert any(a.startswith(CRITIQUE) and "NewsAPI" in a for a in alertes)


def test_taux_de_valides_sous_le_seuil():
    alertes = evalue_alertes(run_normal(nb_valides=80, nb_images_valides=80), appels_newsapi_jour=1)
    assert any(a.startswith(ATTENTION) and "données valides" in a for a in alertes)


def test_taux_de_valides_juste_au_dessus_du_seuil_ne_declenche_pas():
    nb_valides = round(97 * SEUILS["taux_valides_min"]) + 1
    alertes = evalue_alertes(run_normal(nb_valides=nb_valides, nb_images_valides=nb_valides), 1)
    assert not any("données valides" in a for a in alertes)


def test_images_inaccessibles():
    alertes = evalue_alertes(run_normal(nb_images_valides=50), appels_newsapi_jour=1)
    assert any("images accessibles" in a for a in alertes)


def test_run_lent():
    alertes = evalue_alertes(run_normal(duree_transformation_s=400), appels_newsapi_jour=1)
    assert any("run lent" in a for a in alertes)


def test_quota_newsapi_proche():
    alertes = evalue_alertes(run_normal(), appels_newsapi_jour=SEUILS["appels_newsapi_jour_max"] + 1)
    assert any("appels NewsAPI" in a for a in alertes)


def test_division_par_zero_evitee_quand_rien_n_est_extrait():
    alertes = evalue_alertes(
        run_normal(nb_newsapi=0, nb_rss=0, nb_extraits=0, nb_valides=0, nb_images_valides=0), 1
    )
    assert sum(a.startswith(CRITIQUE) for a in alertes) == 2
