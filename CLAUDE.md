# CLAUDE.md — Extraction de données web (CheckIt.AI)

Projet de formation (parcours Data Engineer) : pipeline d'acquisition de publications d'actualité
**multimodales (texte + image)** pour un futur détecteur de fake news. Le brief complet est dans
[enonce.md](enonce.md). Toute la documentation et le code sont en **français** : garder cette langue.

## Avancement par étape de l'énoncé

| Étape | Livrable attendu | État | Où |
|---|---|---|---|
| 1. Explorer les sources | Rapport d'exploration (MD/PDF) | Fait | `docs/01_rapport_exploration_sources.md` |
| 2. Scripts d'extraction | Scripts `.py` modulaires, sans intervention | Fait | `src/extraction/` |
| 3. Pipeline de transformation | Pipeline reproductible et journalisé + schéma conceptuel (Mermaid) | Fait | `src/transformation/`, `docs/02_schema_conceptuel.md` |
| 4. Orchestration Airflow | DAG ETL + chargement en base SQL/NoSQL sécurisée + preuves d'exécution | Fait (captures UI à ajouter dans `docs/captures/`) | `docker-compose.yaml`, `airflow/`, `db/init/`, `src/chargement/`, `docs/03_orchestration_airflow_et_base.md` |
| 5. KPI et monitoring | Dashboard Streamlit + plan de monitoring (MD/PDF) | **À faire** | — |

## Architecture

```
src/extraction/   main.py -> newsapi_extractor.py + rss_extractor.py -> data/raw/extraction_<ts>.json
src/transformation/ main.py (lecture -> traitement -> export) + transform.py -> data/processed/processed_<ts>.csv
src/chargement/   main.py : CSV -> table publications (INSERT ... ON CONFLICT DO NOTHING)
airflow/dags/     checkit_etl.py : extraire >> transformer >> charger (PythonOperator, chemins via XCom)
db/init/          01_init_bases.sh : bases airflow + checkit, rôles, table (1er démarrage du volume)
logs/             extraction.log, transformation.log, chargement.log (logging console + fichier)
docs/             livrables écrits (étapes 1, 3 et 4)
```

- **Docker** : Airflow 3.3.2 en LocalExecutor (api-server, scheduler, dag-processor, init) + `postgres:16-alpine`.
  Dans les conteneurs, le projet est monté dans `/opt/checkit` (`PYTHONPATH=/opt/checkit/src`).
- **Rôles PostgreSQL** : `checkit_etl` (SELECT, INSERT), `checkit_lecteur` (SELECT, pour le dashboard).
  Dans Airflow, les identifiants viennent de la Connection `checkit_postgres` (chiffrée par Fernet).

- **Sources retenues** : NewsAPI (`/v2/everything`, q="France", language=fr, 50 articles par appel)
  et flux RSS (Le Monde, France Info) via `feedparser`. Reddit et FakeNewsNet ne sont que documentés.
- **Schéma commun en sortie d'extraction** : `title, content, image_url, has_valid_image, published_at,
  source_domain, url, source_type, extracted_at`.
- **La transformation** nettoie le HTML et la troncature NewsAPI, normalise les dates en ISO 8601 UTC,
  valide les images par une requête HEAD, calcule `id` = sha256(url)[:16] et déduplique.

## Commandes

`extraction`, `transformation` et `chargement` sont des packages Python : imports absolus (`from extraction.config import ...`),
exécution en module (`python -m`) **depuis `src/`**.

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env            # puis renseigner NEWSAPI_KEY
cd src
../.venv/Scripts/python -m extraction.main
../.venv/Scripts/python -m transformation.main [chemin/fichier_brut.json]   # sans argument : dernier fichier brut
../.venv/Scripts/python -m chargement.main [chemin/fichier.csv]        # nécessite le PostgreSQL Docker

# Orchestration (depuis la racine)
docker compose up -d --build       # UI Airflow : http://localhost:8080, PostgreSQL : localhost:5435
docker compose exec airflow-scheduler airflow dags trigger checkit_etl
docker compose exec postgres psql -U postgres -d checkit
```

## Conventions

- Les secrets restent dans `.env` (ignoré par git). Ne jamais lire ni afficher `.env`.
- Les noms de fonctions de la transformation et du chargement sont en français et en verbe (`nettoie_texte`, `valide_image`),
  ceux de l'extraction en anglais. Respecter la convention du module qu'on modifie.
- Une fonction par responsabilité (connexion, parsing, nettoyage, sauvegarde), avec `try/except`
  et log sur chaque appel réseau.
- Les paramètres (requête, flux, timeouts) vont dans `config.py`, pas dans le code.

## Points d'attention connus

- `extraction`, `transformation` et `chargement` ont chacun un `config.py` et un `common.py`. Toujours les importer
  qualifiés par le package : un import plat (`from config import ...`) recréerait le conflit de noms.
- `valide_image()` fait des HEAD séquentiels : environ 1 seconde par publication (100 publications
  traitées en ~1 min 20). À paralléliser ou mettre en cache si le volume augmente.
- Plan gratuit NewsAPI : 100 requêtes par jour, `content` tronqué, `top-headlines?country=fr` vide.
- Le diagramme Mermaid de `docs/02_schema_conceptuel.md` n'affiche ni `domaine` (SOURCE) ni
  `domaine_source`/`source_type`, alors que les tableaux et le CSV les contiennent.
- Ports 5432 et 5433 déjà pris par un PostgreSQL installé sur Windows : le PostgreSQL Docker est sur 5435.
- En Airflow 3.3, `PostgresHook.get_conn()` renvoie une connexion psycopg 3 : le module `chargement`
  utilise psycopg2 (`execute_values`), donc le DAG ouvre lui-même la connexion psycopg2.
- Fichiers horodatés à la seconde : garder `max_active_runs=1` sur le DAG.
- `db/init/` ne s'exécute que si le volume `postgres-db-volume` est vide (`docker compose down -v` pour rejouer).
- Pas de tests ni de README.
