-- Table de suivi des exécutions du pipeline (étape 5 : KPI et monitoring).
-- Une ligne par run du DAG checkit_etl, écrite par la tâche enregistrer_metriques.
--
-- Exécuté automatiquement au premier démarrage d'un volume vide (après 01_init_bases.sh).
-- Sur une base existante, l'appliquer une fois à la main :
--   docker compose exec -T postgres psql -U postgres < db/init/02_table_executions.sql

\connect checkit

CREATE TABLE IF NOT EXISTS executions (
    run_id                  TEXT         PRIMARY KEY,
    debut                   TIMESTAMPTZ  NOT NULL,
    fin                     TIMESTAMPTZ  NOT NULL,
    statut                  TEXT         NOT NULL CHECK (statut IN ('succes', 'echec')),
    etape_en_echec          TEXT,                       -- NULL si succès

    -- Volumes (précision des données)
    nb_newsapi              INTEGER,
    nb_rss                  INTEGER,
    nb_extraits             INTEGER,
    nb_valides              INTEGER,
    nb_rejetes              INTEGER,
    nb_doublons             INTEGER,
    nb_images_valides       INTEGER,
    nb_nouvelles            INTEGER,
    nb_deja_presentes       INTEGER,

    -- Rapidité (secondes)
    duree_extraction_s      REAL,
    duree_transformation_s  REAL,
    duree_chargement_s      REAL,

    -- Coût (ressources)
    memoire_max_mo          REAL,
    taille_fichiers_ko      REAL,
    appels_newsapi          INTEGER,

    alertes                 TEXT[]       NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_executions_debut ON executions (debut);

-- UPDATE autorisé ici (et seulement ici) : un run relancé depuis l'UI Airflow
-- met à jour sa ligne au lieu d'en créer une seconde.
GRANT SELECT, INSERT, UPDATE ON executions TO checkit_etl;
GRANT SELECT ON executions TO checkit_lecteur;
