# 02 — Database Schema (the Coficab ERD)

> The current `database/schema.sql` is generic and **must be replaced** with the Coficab relational model from the spec image. This is the foundation: every other skill assumes these tables exist.

## Design principles

1. **One source of truth per concept.** No duplicate `livraison` + `demande` tables. Use `demandes_local`.
2. **PostgreSQL ENUMs for fixed vocabularies** — truck status, plan status, mission status. Cheaper than strings, prevents typos.
3. **Numeric for money & weights** — never `FLOAT`. Use `NUMERIC(10,2)` for euros, `NUMERIC(10,2)` for kg.
4. **Indexes on every foreign key + every date column queried by the KPI engine.**
5. **`plan_version` has a status that locks the plan.** Skill 05 enforces it.
6. **KPI tables hold both raw aggregates AND computed values** — so back-fills are possible if formulas change.

---

## File: `database/schema.sql` (replace existing)

```sql
-- ============================================================================
-- Coficab Transport Platform — Relational Schema
-- PostgreSQL 14+
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- ENUMs
-- ---------------------------------------------------------------------------
CREATE TYPE camion_type_enum   AS ENUM ('SEMI', 'PORTEUR', 'FOURGON', 'TAUTLINER');
CREATE TYPE camion_status_enum AS ENUM ('DISPONIBLE', 'EN_MISSION', 'MAINTENANCE', 'PANNE');
CREATE TYPE permis_type_enum   AS ENUM ('B', 'C', 'CE', 'D');
CREATE TYPE chauffeur_status_enum AS ENUM ('ACTIF', 'CONGE', 'ARRET_MALADIE', 'INACTIF');
CREATE TYPE statut_demande_enum AS ENUM ('NOUVELLE', 'PLANIFIEE', 'EN_COURS', 'LIVREE', 'ANNULEE');
CREATE TYPE priorite_enum      AS ENUM ('NORMALE', 'HAUTE', 'URGENTE');
CREATE TYPE statut_plan_enum   AS ENUM ('DRAFT', 'EN_REVUE', 'VALIDE', 'EXECUTE', 'CLOTURE');
CREATE TYPE periode_enum       AS ENUM ('JOUR', 'SEMAINE', 'MOIS');
CREATE TYPE statut_mission_enum AS ENUM ('PLANIFIEE', 'EN_COURS', 'TERMINEE', 'ANNULEE');
CREATE TYPE mode_mission_enum  AS ENUM ('NORMAL', 'PREMIUM');
CREATE TYPE evenement_type_enum AS ENUM (
  'PANNE_VEHICULE','RETARD_TRAFIC','CLIENT_INDISPONIBLE',
  'DEPASSEMENT_CAPACITE','DEMANDE_LAST_MINUTE','CLIENT_COMPLAINT'
);
CREATE TYPE kpi_frequence_enum AS ENUM ('daily','weekly','monthly','yearly');
CREATE TYPE kpi_direction_enum AS ENUM ('UP','DOWN');     -- UP = higher is better
CREATE TYPE kpi_status_enum    AS ENUM ('OK','WARN','ALERT','NA');

-- ---------------------------------------------------------------------------
-- Reference tables
-- ---------------------------------------------------------------------------

-- camions
CREATE TABLE camions (
    id                       SERIAL PRIMARY KEY,
    plate_number             VARCHAR(20) UNIQUE NOT NULL,
    type                     camion_type_enum NOT NULL,
    capacite_kg              NUMERIC(10,2) NOT NULL,
    max_palettes             SMALLINT NOT NULL,
    status                   camion_status_enum NOT NULL DEFAULT 'DISPONIBLE',
    consommation_base_l_100km NUMERIC(5,2),     -- baseline fuel consumption
    chauffeur_defaut_id      INTEGER,           -- FK below (deferred)
    date_creation            TIMESTAMPTZ DEFAULT now()
);

-- chauffeurs
CREATE TABLE chauffeurs (
    id                INTEGER PRIMARY KEY,      -- matriculé interne
    full_name         TEXT NOT NULL,
    phone             VARCHAR(30),
    permis_type       permis_type_enum NOT NULL,
    permis_numero     VARCHAR(50),
    status            chauffeur_status_enum NOT NULL DEFAULT 'ACTIF',
    camion_defaut_id  INTEGER REFERENCES camions(id),
    shift_start       TIME,
    shift_end         TIME,
    date_creation     TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE camions
  ADD CONSTRAINT camion_chauffeur_defaut_fk
  FOREIGN KEY (chauffeur_defaut_id) REFERENCES chauffeurs(id);

-- clients
CREATE TABLE clients (
    id                INTEGER PRIMARY KEY,      -- client_id business code
    nom               TEXT NOT NULL,
    address           TEXT,
    city              TEXT,
    country           TEXT,
    email             VARCHAR(100),
    numero            VARCHAR(30),               -- phone
    latitude          NUMERIC(9,6),
    longitude         NUMERIC(9,6),
    fenetre_ouverture TIME,                      -- time window open
    fenetre_fermeture TIME,                      -- time window close
    exigences         TEXT,                      -- special requirements
    date_creation     TIMESTAMPTZ DEFAULT now()
);

-- affectation_chauffeur (driver default truck assignments, historical)
CREATE TABLE affectation_chauffeur (
    id              SERIAL PRIMARY KEY,
    chauffeur_id    INTEGER NOT NULL REFERENCES chauffeurs(id),
    camion_id       INTEGER NOT NULL REFERENCES camions(id),
    date_affectation DATE NOT NULL
);

-- ---------------------------------------------------------------------------
-- Operational tables
-- ---------------------------------------------------------------------------

-- demandes_local (delivery requests)
CREATE TABLE demandes_local (
    id                       SERIAL PRIMARY KEY,
    client_id                INTEGER NOT NULL REFERENCES clients(id),
    quantite_kg              NUMERIC(10,2) NOT NULL,
    nombre_palettes          SMALLINT,
    date_livraison           DATE NOT NULL,
    heure_arrivee_prevue     TIMESTAMPTZ,           -- planned arrival
    heure_arrivee_reelle     TIMESTAMPTZ,           -- actual arrival
    quantite_livree_kg       NUMERIC(10,2),         -- filled on close-out
    commentaire              TEXT,
    statut                   statut_demande_enum NOT NULL DEFAULT 'NOUVELLE',
    priorite                 priorite_enum NOT NULL DEFAULT 'NORMALE',
    livree_a_temps           BOOLEAN,                -- derived on close-out
    source_import            VARCHAR(50),            -- 'excel', 'email', 'manual'
    date_creation            TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_demandes_date     ON demandes_local(date_livraison);
CREATE INDEX idx_demandes_client   ON demandes_local(client_id);
CREATE INDEX idx_demandes_statut   ON demandes_local(statut);

-- plan_version (a planning iteration, holds the lifecycle)
CREATE TABLE plan_version (
    id              SERIAL PRIMARY KEY,
    plan_id         INTEGER NOT NULL,           -- logical plan grouping
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
CREATE INDEX idx_planv_status ON plan_version(statut_plan);
CREATE INDEX idx_planv_period ON plan_version(date_debut, date_fin);

-- plan_mission (one truck-route per (truck, day))
CREATE TABLE plan_mission (
    id                       SERIAL PRIMARY KEY,
    plan_version_id          INTEGER NOT NULL REFERENCES plan_version(id) ON DELETE CASCADE,
    camion_id                INTEGER NOT NULL REFERENCES camions(id),
    chauffeur_id             INTEGER NOT NULL REFERENCES chauffeurs(id),
    date_mission             DATE NOT NULL,
    heure_sortie_prevue      TIMESTAMPTZ,
    heure_sortie_reelle      TIMESTAMPTZ,
    heure_retour_prevue      TIMESTAMPTZ,
    heure_retour_reelle      TIMESTAMPTZ,
    statut                   statut_mission_enum NOT NULL DEFAULT 'PLANIFIEE',
    mode                     mode_mission_enum NOT NULL DEFAULT 'NORMAL',
    -- physical
    km_parcourus             NUMERIC(8,2),
    km_a_vide                NUMERIC(8,2),
    charge_kg                NUMERIC(10,2),
    charge_palettes          SMALLINT,
    fuel_consomme_l          NUMERIC(8,2),
    -- costs (€/T contributors)
    cout_consommables_eur    NUMERIC(10,2) DEFAULT 0,
    cout_emballage_eur       NUMERIC(10,2) DEFAULT 0,
    cout_transport_eur       NUMERIC(10,2) DEFAULT 0,
    cout_premium_eur         NUMERIC(10,2) DEFAULT 0,
    -- KPI snapshot (computed at close-out, denormalised for fast read)
    load_eff_kg_pct          NUMERIC(5,2),
    load_eff_pallets_pct     NUMERIC(5,2),
    load_eff_pct             NUMERIC(5,2)        -- max(kg, pallets)
);
CREATE INDEX idx_mission_date     ON plan_mission(date_mission);
CREATE INDEX idx_mission_version  ON plan_mission(plan_version_id);
CREATE INDEX idx_mission_camion   ON plan_mission(camion_id, date_mission);

-- mission_demande (which demandes are served by which mission, in order)
CREATE TABLE mission_demande (
    id                  SERIAL PRIMARY KEY,
    mission_id          INTEGER NOT NULL REFERENCES plan_mission(id) ON DELETE CASCADE,
    demande_id          INTEGER NOT NULL REFERENCES demandes_local(id),
    ordre_livraison     SMALLINT NOT NULL,        -- stop sequence (1, 2, 3, ...)
    eta_prevue          TIMESTAMPTZ,
    eta_reelle          TIMESTAMPTZ,
    statut              statut_demande_enum NOT NULL DEFAULT 'PLANIFIEE',
    UNIQUE (mission_id, ordre_livraison)
);
CREATE INDEX idx_md_mission ON mission_demande(mission_id);
CREATE INDEX idx_md_demande ON mission_demande(demande_id);

-- evenement_alea (incidents / disruptions)
CREATE TABLE evenement_alea (
    id                   SERIAL PRIMARY KEY,
    plan_version_id      INTEGER REFERENCES plan_version(id),
    mission_id           INTEGER REFERENCES plan_mission(id),
    demande_id           INTEGER REFERENCES demandes_local(id),
    type                 evenement_type_enum NOT NULL,
    description          TEXT,
    date_evenement       TIMESTAMPTZ NOT NULL DEFAULT now(),
    impact_delai_min     INTEGER DEFAULT 0,        -- estimated delay added
    resolu               BOOLEAN DEFAULT FALSE,
    date_resolution      TIMESTAMPTZ,
    cause                TEXT
);
CREATE INDEX idx_event_type ON evenement_alea(type);
CREATE INDEX idx_event_date ON evenement_alea(date_evenement);

-- ---------------------------------------------------------------------------
-- KPI tables (see skill 01 for formulas)
-- ---------------------------------------------------------------------------

CREATE TABLE kpi_definition (
    id            SERIAL PRIMARY KEY,
    code          VARCHAR(20) UNIQUE NOT NULL,     -- 'R4-06', 'R4-02', 'R4-13', …
    nom           TEXT NOT NULL,
    description   TEXT,
    unite         VARCHAR(20) NOT NULL,
    frequence     kpi_frequence_enum NOT NULL,
    direction     kpi_direction_enum NOT NULL,
    target_2025   NUMERIC(10,4),
    -- For direction='UP': green if value >= green_min, yellow if >= yellow_min
    green_min     NUMERIC(10,4),
    yellow_min    NUMERIC(10,4),
    -- For direction='DOWN': green if value <= green_max, yellow if <= yellow_max
    green_max     NUMERIC(10,4),
    yellow_max    NUMERIC(10,4),
    date_creation TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE kpi_journalier (
    id              SERIAL PRIMARY KEY,
    kpi_def_id      INTEGER NOT NULL REFERENCES kpi_definition(id),
    date_mesure     DATE NOT NULL,
    plant           VARCHAR(50),
    valeur          NUMERIC(12,4),
    color           VARCHAR(10),                   -- 'green' | 'yellow' | 'red' | 'grey'
    -- Raw aggregates (so we can re-compute if formula changes)
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
CREATE INDEX idx_kpi_j_date ON kpi_journalier(date_mesure);
CREATE INDEX idx_kpi_j_def  ON kpi_journalier(kpi_def_id);

CREATE TABLE kpi_mensuel (
    id            SERIAL PRIMARY KEY,
    kpi_def_id    INTEGER NOT NULL REFERENCES kpi_definition(id),
    annee         SMALLINT NOT NULL,
    mois          SMALLINT NOT NULL,                 -- 1-12
    plant         VARCHAR(50),
    valeur        NUMERIC(12,4),
    target        NUMERIC(12,4),
    status        kpi_status_enum NOT NULL DEFAULT 'NA',
    color         VARCHAR(10),
    date_calcul   TIMESTAMPTZ DEFAULT now(),
    UNIQUE (kpi_def_id, annee, mois, plant)
);
CREATE INDEX idx_kpi_m_period ON kpi_mensuel(annee, mois);

-- ---------------------------------------------------------------------------
-- Auth (kept minimal; see skill 11)
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(100) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(30) NOT NULL DEFAULT 'viewer',   -- 'planner' | 'viewer' | 'admin'
    is_active       BOOLEAN DEFAULT TRUE,
    date_creation   TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Audit (governance trail required by spec §5.6)
-- ---------------------------------------------------------------------------
CREATE TABLE planning_change_log (
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
CREATE INDEX idx_pcl_version ON planning_change_log(plan_version_id);
```

---

## ORM mapping (SQLAlchemy)

`backend/app/models/__init__.py` should export every model so `Base.metadata.create_all` picks them up. One file per concern keeps things readable.

Skeleton for `backend/app/models/camion.py`:

```python
from sqlalchemy import Column, Integer, String, Numeric, SmallInteger, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class CamionType(str, enum.Enum):
    SEMI = "SEMI"; PORTEUR = "PORTEUR"; FOURGON = "FOURGON"; TAUTLINER = "TAUTLINER"

class CamionStatus(str, enum.Enum):
    DISPONIBLE = "DISPONIBLE"; EN_MISSION = "EN_MISSION"
    MAINTENANCE = "MAINTENANCE"; PANNE = "PANNE"

class Camion(Base):
    __tablename__ = "camions"
    id = Column(Integer, primary_key=True)
    plate_number = Column(String(20), unique=True, nullable=False)
    type = Column(Enum(CamionType, name="camion_type_enum"), nullable=False)
    capacite_kg = Column(Numeric(10,2), nullable=False)
    max_palettes = Column(SmallInteger, nullable=False)
    status = Column(Enum(CamionStatus, name="camion_status_enum"),
                    nullable=False, default=CamionStatus.DISPONIBLE)
    consommation_base_l_100km = Column(Numeric(5,2))
    chauffeur_defaut_id = Column(Integer, ForeignKey("chauffeurs.id"))
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

    missions = relationship("PlanMission", back_populates="camion")
    chauffeur_defaut = relationship(
        "Chauffeur", foreign_keys=[chauffeur_defaut_id], post_update=True
    )
```

Use the same shape for `Chauffeur`, `Client`, `DemandeLocal`, `PlanVersion`, `PlanMission`, `MissionDemande`, `EvenementAlea`, `KpiDefinition`, `KpiJournalier`, `KpiMensuel`. Skill 12 has a fixtures script you can grow into a seed.

---

## Migration from current schema

1. **Back up** any data in the existing `livraison` / `ingestion_log` tables if you care about it.
2. Drop the old tables: `users, agents, events, tasks, alerts, planning_versions, planning_change_logs`. The new schema re-introduces `users` and `planning_change_log` with the right shape.
3. Apply the new `schema.sql`.
4. Seed `kpi_definition` (skill 01) and demo `camions / chauffeurs / clients` (`database/seed_demo.sql`).
5. The Excel watcher will populate `demandes_local` from `weekly planning/`.

---

## Future schema changes (Alembic)

`schema.sql` represents the **initial state** only. Any column or table change after the first deploy must go through an Alembic migration — never re-run or edit `schema.sql` on an existing database.

```bash
# One-time setup (run from backend/)
pip install alembic
alembic init alembic
# In alembic/env.py: point target_metadata at Base.metadata from app.database
# In alembic.ini: set sqlalchemy.url = postgresql://...
```

Then for every schema change:
```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

See skill [13 — Rule 2](13-collaboration-and-merging.md): migrations are append-only. Never edit a committed migration file; write a follow-up migration instead.

---

## Indexes worth their weight

Every WHERE clause the KPI engine uses must hit an index. The schema above already covers:
- `demandes_local(date_livraison)` — daily OTD/OTIF
- `plan_mission(date_mission)` — daily fuel/load efficiency
- `evenement_alea(type, date_evenement)` — monthly R4-12
- `kpi_journalier(kpi_def_id, date_mesure)` — dashboard reads

Don't add more until you see a slow query in `EXPLAIN ANALYZE`.

---

## Verification

```sql
-- Should return 8 (the catalog)
SELECT count(*) FROM kpi_definition;

-- Should return at least 1 truck + 1 driver + 1 client for local dev
SELECT count(*) FROM camions;
SELECT count(*) FROM chauffeurs;
SELECT count(*) FROM clients;

-- Should be 0 until the optimizer runs (skill 04)
SELECT count(*) FROM plan_version;
```
