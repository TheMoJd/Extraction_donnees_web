#!/bin/bash
# Exécuté une seule fois par l'image postgres, au premier démarrage (volume vide).
# Crée les bases, les rôles à privilèges minimaux et la table des publications.
#
# Les mots de passe sont passés à psql en variables (-v), puis insérés avec :'variable',
# ce qui les échappe correctement : ils n'apparaissent jamais en clair dans ce fichier.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v airflow_pwd="$AIRFLOW_DB_PASSWORD" \
  -v etl_pwd="$CHECKIT_ETL_PASSWORD" \
  -v lecteur_pwd="$CHECKIT_LECTEUR_PASSWORD" <<'EOSQL'

-- Base des métadonnées Airflow, réservée au rôle airflow.
CREATE ROLE airflow LOGIN PASSWORD :'airflow_pwd';
CREATE DATABASE airflow OWNER airflow;
REVOKE ALL ON DATABASE airflow FROM PUBLIC;

-- Base métier : seuls les deux rôles CheckIt peuvent s'y connecter.
CREATE ROLE checkit_etl LOGIN PASSWORD :'etl_pwd';          -- le pipeline : lit et insère
CREATE ROLE checkit_lecteur LOGIN PASSWORD :'lecteur_pwd';  -- le dashboard : lit seulement
CREATE DATABASE checkit;
REVOKE ALL ON DATABASE checkit FROM PUBLIC;
GRANT CONNECT ON DATABASE checkit TO checkit_etl, checkit_lecteur;

\connect checkit

-- Personne d'autre que le superutilisateur ne peut créer de tables.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO checkit_etl, checkit_lecteur;

-- Schéma physique de l'entité PUBLICATION (voir docs/02 et docs/03).
CREATE TABLE publications (
    id                CHAR(16)     PRIMARY KEY,           -- sha256(url)[:16]
    titre             TEXT         NOT NULL,
    contenu           TEXT,
    longueur_contenu  INTEGER      CHECK (longueur_contenu >= 0),
    image_url         TEXT,
    image_valide      BOOLEAN      NOT NULL DEFAULT FALSE,
    date_publication  TIMESTAMPTZ,
    domaine_source    TEXT,
    url               TEXT         NOT NULL UNIQUE,
    source_type       TEXT         NOT NULL CHECK (source_type IN ('newsapi', 'rss')),
    transforme_at     TIMESTAMPTZ  NOT NULL,
    charge_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_publications_date_publication ON publications (date_publication);
CREATE INDEX idx_publications_source_type ON publications (source_type);

-- Moindre privilège : pas de DELETE, UPDATE ni DDL pour le pipeline.
GRANT SELECT, INSERT ON publications TO checkit_etl;
GRANT SELECT ON publications TO checkit_lecteur;
EOSQL
