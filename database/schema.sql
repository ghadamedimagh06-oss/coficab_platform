-- ============================================================================
-- Coficab Transport Platform — Relational Schema
-- PostgreSQL 14+
-- Run with: psql -U postgres -d coficab_db -f schema.sql
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- ENUMs
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE TYPE camion_type_enum   AS ENUM ('SEMI','PORTEUR','FOURGON','TAUTLINER');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE camion_status_enum AS ENUM ('DISPONIBLE','EN_MISSION','MAINTENANCE','PANNE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE permis_type_enum   AS ENUM ('B','C','CE','D');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE chauffeur_status_enum AS ENUM ('ACTIF','CONGE','ARRET_MALADIE','INACTIF');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE statut_demande_enum AS ENUM ('NOUVELLE','PLANIFIEE','EN_COURS','LIVREE','ANNULEE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE priorite_enum      AS ENUM ('NORMALE','HAUTE','URGENTE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE statut_plan_enum   AS ENUM ('DRAFT','EN_REVUE','VALIDE','EXECUTE','CLOTURE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE periode_enum       AS ENUM ('JOUR','SEMAINE','MOIS');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE statut_mission_enum AS ENUM ('PLANIFIEE','EN_COURS','TERMINEE','ANNULEE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE mode_mission_enum  AS ENUM ('NORMAL','PREMIUM');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE evenement_type_enum AS ENUM (
    'PANNE_VEHICULE','RETARD_TRAFIC','CLIENT_INDISPONIBLE',
    'DEPASSEMENT_CAPACITE','DEMANDE_LAST_MINUTE','CLIENT_COMPLAINT'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE kpi_frequence_enum AS ENUM ('daily','weekly','monthly','yearly');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE kpi_direction_enum AS ENUM ('UP','DOWN');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE kpi_status_enum    AS ENUM ('OK','WARN','ALERT','NA');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------------------
-- Auth
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(100) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(30) NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN DEFAULT TRUE,
    date_creation   TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Reference tables
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS camions (
    id                        SERIAL PRIMARY KEY,
    plate_number              VARCHAR(20) UNIQUE NOT NULL,
    type                      camion_type_enum NOT NULL,
    capacite_kg               NUMERIC(10,2) NOT NULL,
    max_palettes              SMALLINT NOT NULL,
    status                    camion_status_enum NOT NULL DEFAULT 'DISPONIBLE',
    consommation_base_l_100km NUMERIC(5,2),
    chauffeur_defaut_id       INTEGER,
    date_creation             TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chauffeurs (
    id               INTEGER PRIMARY KEY,
    full_name        TEXT NOT NULL,
    phone            VARCHAR(30),
    permis_type      permis_type_enum NOT NULL,
    permis_numero    VARCHAR(50) UNIQUE,
    status           chauffeur_status_enum NOT NULL DEFAULT 'ACTIF',
    camion_defaut_id INTEGER UNIQUE REFERENCES camions(id),
    shift_start      TIME,
    shift_end        TIME,
    date_creation    TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE camions
  ADD CONSTRAINT IF NOT EXISTS camion_chauffeur_defaut_fk
  FOREIGN KEY (chauffeur_defaut_id) REFERENCES chauffeurs(id);

CREATE TABLE IF NOT EXISTS clients (
    id                INTEGER PRIMARY KEY,
    nom               TEXT NOT NULL,
    address           TEXT,
    city              TEXT,
    country           TEXT,
    email             VARCHAR(100),
    numero            VARCHAR(30),
    latitude          NUMERIC(9,6),
    longitude         NUMERIC(9,6),
    fenetre_ouverture TIME,
    fenetre_fermeture TIME,
    exigences         TEXT,
    date_creation     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS affectation_chauffeur (
    id               SERIAL PRIMARY KEY,
    chauffeur_id     INTEGER NOT NULL REFERENCES chauffeurs(id),
    camion_id        INTEGER NOT NULL REFERENCES camions(id),
    date_affectation DATE NOT NULL
);

-- ---------------------------------------------------------------------------
-- Operational tables
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS demandes_local (
    id                   SERIAL PRIMARY KEY,
    client_id            INTEGER NOT NULL REFERENCES clients(id),
    quantite_kg          NUMERIC(10,2) NOT NULL,
    nombre_palettes      SMALLINT,
    date_livraison       DATE NOT NULL,
    heure_arrivee_prevue TIMESTAMPTZ,
    heure_arrivee_reelle TIMESTAMPTZ,
    quantite_livree_kg   NUMERIC(10,2),
    commentaire          TEXT,
    statut               statut_demande_enum NOT NULL DEFAULT 'NOUVELLE',
    priorite             priorite_enum NOT NULL DEFAULT 'NORMALE',
    livree_a_temps       BOOLEAN,
    source_import        VARCHAR(50),
    date_creation        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_demandes_date   ON demandes_local(date_livraison);
CREATE INDEX IF NOT EXISTS idx_demandes_client ON demandes_local(client_id);
CREATE INDEX IF NOT EXISTS idx_demandes_statut ON demandes_local(statut);

CREATE TABLE IF NOT EXISTS plan_version (
    id              SERIAL PRIMARY KEY,
    plan_id         INTEGER NOT NULL,
    version_number  SMALLINT NOT NULL,
    periode         periode_enum NOT NULL,
    date_debut      DATE NOT NULL,
    date_fin        DATE NOT NULL,
    statut_plan     statut_plan_enum NOT NULL DEFAULT 'DRAFT',
    date_creation   TIMESTAMPTZ DEFAULT now(),
    date_validation TIMESTAMPTZ,
    valide_par      VARCHAR(100),
    commentaire     TEXT,
    UNIQUE (plan_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_planv_status ON plan_version(statut_plan);
CREATE INDEX IF NOT EXISTS idx_planv_period ON plan_version(date_debut, date_fin);

CREATE TABLE IF NOT EXISTS plan_mission (
    id                    SERIAL PRIMARY KEY,
    plan_version_id       INTEGER NOT NULL REFERENCES plan_version(id) ON DELETE CASCADE,
    camion_id             INTEGER NOT NULL REFERENCES camions(id),
    chauffeur_id          INTEGER NOT NULL REFERENCES chauffeurs(id),
    date_mission          DATE NOT NULL,
    heure_sortie_prevue   TIMESTAMPTZ,
    heure_sortie_reelle   TIMESTAMPTZ,
    heure_retour_prevue   TIMESTAMPTZ,
    heure_retour_reelle   TIMESTAMPTZ,
    statut                statut_mission_enum NOT NULL DEFAULT 'PLANIFIEE',
    mode                  mode_mission_enum NOT NULL DEFAULT 'NORMAL',
    km_parcourus          NUMERIC(8,2),
    km_a_vide             NUMERIC(8,2),
    charge_kg             NUMERIC(10,2),
    charge_palettes       SMALLINT,
    fuel_consomme_l       NUMERIC(8,2),
    cout_consommables_eur NUMERIC(10,2) DEFAULT 0,
    cout_emballage_eur    NUMERIC(10,2) DEFAULT 0,
    cout_transport_eur    NUMERIC(10,2) DEFAULT 0,
    cout_premium_eur      NUMERIC(10,2) DEFAULT 0,
    load_eff_kg_pct       NUMERIC(5,2),
    load_eff_pallets_pct  NUMERIC(5,2),
    load_eff_pct          NUMERIC(5,2)
);
CREATE INDEX IF NOT EXISTS idx_mission_date    ON plan_mission(date_mission);
CREATE INDEX IF NOT EXISTS idx_mission_version ON plan_mission(plan_version_id);
CREATE INDEX IF NOT EXISTS idx_mission_camion  ON plan_mission(camion_id, date_mission);

CREATE TABLE IF NOT EXISTS mission_demande (
    id              SERIAL PRIMARY KEY,
    mission_id      INTEGER NOT NULL REFERENCES plan_mission(id) ON DELETE CASCADE,
    demande_id      INTEGER NOT NULL REFERENCES demandes_local(id),
    ordre_livraison SMALLINT NOT NULL,
    eta_prevue      TIMESTAMPTZ,
    eta_reelle      TIMESTAMPTZ,
    statut          statut_demande_enum NOT NULL DEFAULT 'PLANIFIEE',
    UNIQUE (mission_id, ordre_livraison)
);
CREATE INDEX IF NOT EXISTS idx_md_mission ON mission_demande(mission_id);
CREATE INDEX IF NOT EXISTS idx_md_demande ON mission_demande(demande_id);

CREATE TABLE IF NOT EXISTS evenement_alea (
    id               SERIAL PRIMARY KEY,
    plan_version_id  INTEGER REFERENCES plan_version(id),
    mission_id       INTEGER REFERENCES plan_mission(id),
    demande_id       INTEGER REFERENCES demandes_local(id),
    type             evenement_type_enum NOT NULL,
    description      TEXT,
    date_evenement   TIMESTAMPTZ NOT NULL DEFAULT now(),
    impact_delai_min INTEGER DEFAULT 0,
    resolu           BOOLEAN DEFAULT FALSE,
    date_resolution  TIMESTAMPTZ,
    cause            TEXT
);
CREATE INDEX IF NOT EXISTS idx_event_type ON evenement_alea(type);
CREATE INDEX IF NOT EXISTS idx_event_date ON evenement_alea(date_evenement);

CREATE TABLE IF NOT EXISTS rental_approval (
    id                 SERIAL PRIMARY KEY,
    plan_id            VARCHAR(100) NOT NULL,
    day                DATE NOT NULL,
    recommendation_id  VARCHAR(100) NOT NULL,
    rental_profile     VARCHAR(50) NOT NULL,
    estimated_cost_eur NUMERIC(10,2) NOT NULL,
    approved_by        VARCHAR(100) NOT NULL,
    created_at         TIMESTAMPTZ DEFAULT now(),
    UNIQUE (plan_id, recommendation_id)
);
CREATE INDEX IF NOT EXISTS idx_rental_approval_plan ON rental_approval(plan_id);
CREATE INDEX IF NOT EXISTS idx_rental_approval_day ON rental_approval(day);
CREATE UNIQUE INDEX IF NOT EXISTS uq_rental_approval_plan_recommendation
ON rental_approval(plan_id, recommendation_id);

-- ---------------------------------------------------------------------------
-- KPI tables
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kpi_definition (
    id            SERIAL PRIMARY KEY,
    code          VARCHAR(20) UNIQUE NOT NULL,
    nom           TEXT NOT NULL,
    description   TEXT,
    unite         VARCHAR(20) NOT NULL,
    frequence     kpi_frequence_enum NOT NULL,
    direction     kpi_direction_enum NOT NULL,
    target_2025   NUMERIC(10,4),
    green_min     NUMERIC(10,4),
    yellow_min    NUMERIC(10,4),
    green_max     NUMERIC(10,4),
    yellow_max    NUMERIC(10,4),
    date_creation TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kpi_journalier (
    id              SERIAL PRIMARY KEY,
    kpi_def_id      INTEGER NOT NULL REFERENCES kpi_definition(id),
    date_mesure     DATE NOT NULL,
    plant           VARCHAR(50),
    valeur          NUMERIC(12,4),
    color           VARCHAR(10),
    qte_total_kg    NUMERIC(12,2),
    qte_livree_kg   NUMERIC(12,2),
    qte_a_temps_kg  NUMERIC(12,2),
    fuel_consomme_l NUMERIC(12,2),
    km_parcourus    NUMERIC(12,2),
    km_a_vide       NUMERIC(12,2),
    nb_incidents    INTEGER,
    nb_missions     INTEGER,
    cout_total_eur  NUMERIC(12,2),
    date_calcul     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (kpi_def_id, date_mesure, plant)
);
CREATE INDEX IF NOT EXISTS idx_kpi_j_date ON kpi_journalier(date_mesure);
CREATE INDEX IF NOT EXISTS idx_kpi_j_def  ON kpi_journalier(kpi_def_id);

CREATE TABLE IF NOT EXISTS kpi_mensuel (
    id          SERIAL PRIMARY KEY,
    kpi_def_id  INTEGER NOT NULL REFERENCES kpi_definition(id),
    annee       SMALLINT NOT NULL,
    mois        SMALLINT NOT NULL,
    plant       VARCHAR(50),
    valeur      NUMERIC(12,4),
    target      NUMERIC(12,4),
    status      kpi_status_enum NOT NULL DEFAULT 'NA',
    color       VARCHAR(10),
    date_calcul TIMESTAMPTZ DEFAULT now(),
    UNIQUE (kpi_def_id, annee, mois, plant)
);
CREATE INDEX IF NOT EXISTS idx_kpi_m_period ON kpi_mensuel(annee, mois);

-- ---------------------------------------------------------------------------
-- Audit
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS planning_change_log (
    id              SERIAL PRIMARY KEY,
    plan_version_id INTEGER NOT NULL REFERENCES plan_version(id),
    field_changed   VARCHAR(100) NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    reason_category VARCHAR(50),
    reason_text     TEXT,
    user_id         INTEGER REFERENCES users(id),
    timestamp       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pcl_version ON planning_change_log(plan_version_id);

-- ---------------------------------------------------------------------------
-- Dispatch notification log (driver mission brief attempts)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_log (
    id           SERIAL PRIMARY KEY,
    mission_id   INTEGER NOT NULL REFERENCES plan_mission(id),
    chauffeur_id INTEGER NOT NULL REFERENCES chauffeurs(id),
    status       VARCHAR(20) NOT NULL,
    error        TEXT,
    body         TEXT,
    sent_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notification_mission ON notification_log(mission_id);
CREATE INDEX IF NOT EXISTS idx_notification_sent_at ON notification_log(sent_at);

-- ---------------------------------------------------------------------------
-- Ingestion log (tracks file-level import operations)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_logs (
    id            SERIAL PRIMARY KEY,
    file_name     VARCHAR(255) NOT NULL,
    file_path     VARCHAR(500) NOT NULL,
    import_date   TIMESTAMPTZ DEFAULT now(),
    status        VARCHAR(20) NOT NULL,
    inserted_rows INTEGER DEFAULT 0,
    total_rows    INTEGER DEFAULT 0,
    error_message TEXT,
    processed_at  TIMESTAMPTZ,
    archived_path VARCHAR(500)
);
