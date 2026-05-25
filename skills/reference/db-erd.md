# Reference — Entity Relationship Diagram

Text rendering of the Coficab schema. For the DDL, see skill 02.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   camions    │◄───►│  chauffeurs  │     │     clients      │
│              │     │              │     │                  │
│ id (PK)      │     │ id (PK)      │     │ id (PK)          │
│ plate_number │     │ full_name    │     │ nom              │
│ type ENUM    │     │ phone        │     │ address, city    │
│ capacite_kg  │     │ permis_type  │     │ latitude, lon    │
│ max_palettes │     │ status       │     │ fenetre_ouv      │
│ status ENUM  │     │ camion_defaut│─────│ fenetre_ferm     │
│ chauffeur_   │     │ shift_start  │     │ exigences        │
│  defaut_id   │     │ shift_end    │     └──────────────────┘
└──────────────┘     └──────────────┘              ▲
       ▲                    ▲                       │
       │                    │                       │
       │                    │              ┌─────────────────────┐
       │                    │              │   demandes_local    │
       │                    │              │                     │
       │                    │              │ id (PK)             │
       │                    │              │ client_id (FK)──────┘
       │                    │              │ quantite_kg
       │                    │              │ nombre_palettes
       │                    │              │ date_livraison
       │                    │              │ heure_arrivee_prevue
       │                    │              │ heure_arrivee_reelle
       │                    │              │ quantite_livree_kg
       │                    │              │ statut ENUM
       │                    │              │ priorite ENUM
       │                    │              │ livree_a_temps
       │                    │              │ source_import
       │                    │              └─────────────────────┘
       │                    │                       ▲
       │                    │                       │
       │                    │             ┌─────────┴─────────┐
       │                    │             │ mission_demande   │
       │                    │             │                   │
       │                    │             │ id (PK)           │
       │                    │             │ mission_id (FK)───┐
       │                    │             │ demande_id (FK)   │
       │                    │             │ ordre_livraison   │
       │                    │             │ eta_prevue        │
       │                    │             │ eta_reelle        │
       │                    │             │ statut            │
       │                    │             └───────────────────┘
       │                    │                                  │
       │                    │                                  │
       │           ┌────────┴─────────┐                        │
       │           │   plan_mission   │◄───────────────────────┘
       │           │                  │
       └───────────│ camion_id (FK)   │
                   │ chauffeur_id (FK)│
                   │ plan_version_id  │──┐
                   │ date_mission     │  │
                   │ heure_sortie_*   │  │
                   │ heure_retour_*   │  │
                   │ statut ENUM      │  │
                   │ mode ENUM        │  │
                   │ km_parcourus     │  │       ┌─────────────────┐
                   │ km_a_vide        │  │       │   plan_version  │
                   │ charge_kg        │  └──────►│                 │
                   │ charge_palettes  │          │ id (PK)         │
                   │ fuel_consomme_l  │          │ plan_id         │
                   │ cout_consommables│          │ version_number  │
                   │ cout_emballage   │          │ periode ENUM    │
                   │ cout_transport   │          │ date_debut/fin  │
                   │ cout_premium     │          │ statut_plan ENUM│
                   │ load_eff_kg_pct  │          │ date_creation   │
                   │ load_eff_plt_pct │          │ date_validation │
                   │ load_eff_pct     │          │ valide_par      │
                   └──────────────────┘          └─────────────────┘
                            ▲                            ▲
                            │                            │
                  ┌─────────┴────────────────┐  ┌────────┴────────────────┐
                  │     evenement_alea       │  │  planning_change_log    │
                  │                          │  │                         │
                  │ id (PK)                  │  │ id (PK)                 │
                  │ plan_version_id (FK)     │  │ plan_version_id (FK)    │
                  │ mission_id (FK)          │  │ field_changed           │
                  │ demande_id (FK)          │  │ old_value, new_value    │
                  │ type ENUM                │  │ reason_category         │
                  │ description              │  │ reason_text             │
                  │ date_evenement           │  │ user_id (FK)            │
                  │ impact_delai_min         │  │ timestamp               │
                  │ resolu                   │  └─────────────────────────┘
                  │ date_resolution          │
                  │ cause                    │
                  └──────────────────────────┘


┌────────────────────┐      ┌────────────────────┐      ┌────────────────────┐
│  kpi_definition    │◄─────│  kpi_journalier    │      │   kpi_mensuel      │
│                    │      │                    │      │                    │
│ id (PK)            │      │ id (PK)            │      │ id (PK)            │
│ code (R4-06,..)    │      │ kpi_def_id (FK)    │      │ kpi_def_id (FK)────┘
│ nom, description   │      │ date_mesure        │      │ annee, mois
│ unite              │      │ plant              │      │ plant
│ frequence          │      │ valeur, color      │      │ valeur, target
│ direction (UP/DN)  │      │ qte_total_kg       │      │ status, color
│ target_2025        │      │ qte_livree_kg      │      │ date_calcul
│ green/yellow_*     │      │ qte_a_temps_kg     │      └────────────────────┘
└────────────────────┘      │ fuel_consomme_l    │
                            │ km_parcourus       │
                            │ nb_incidents       │
                            │ nb_missions        │
                            │ cout_total_eur     │
                            │ date_calcul        │
                            └────────────────────┘


┌──────────────┐        ┌──────────────────────┐
│    users     │        │  notification_log    │
│              │        │                      │
│ id (PK)      │        │ id (PK)              │
│ username     │        │ mission_id (FK)      │
│ email        │        │ chauffeur_id (FK)    │
│ password_hash│        │ status (sent/failed) │
│ role         │        │ error                │
│ is_active    │        │ sent_at              │
└──────────────┘        └──────────────────────┘
```

## Cardinalities

- `chauffeurs` ◀▶ `camions`: one-to-one default (a driver has a default truck, a truck has a default driver). Historical assignments live in `affectation_chauffeur`.
- `clients` ◀▶ `demandes_local`: one-to-many.
- `plan_version` ◀▶ `plan_mission`: one-to-many.
- `plan_mission` ◀▶ `mission_demande`: one-to-many. Stops in `ordre_livraison`.
- `demandes_local` ◀▶ `mission_demande`: one-to-many in theory (split deliveries) but typically one-to-one in v1.
- `evenement_alea` references **any** of plan, mission, or demande — at least one must be set.
- `kpi_definition` ◀▶ `kpi_journalier`: one-to-many. UNIQUE (kpi_def_id, date_mesure, plant).
- `kpi_definition` ◀▶ `kpi_mensuel`: one-to-many. UNIQUE (kpi_def_id, annee, mois, plant).

## Indexing (already in schema, here for reference)

- `demandes_local(date_livraison)` — every KPI daily aggregate
- `demandes_local(client_id)` — client history view
- `plan_mission(date_mission)` — daily KPI loop
- `plan_mission(plan_version_id)` — plan editor reads
- `evenement_alea(type, date_evenement)` — R4-12 monthly query
- `kpi_journalier(kpi_def_id, date_mesure)` — dashboard reads
- `kpi_mensuel(annee, mois)` — analytics page

## ENUM catalog (centralized list)

| ENUM type | Values |
|---|---|
| `camion_type_enum` | SEMI, PORTEUR, FOURGON, TAUTLINER |
| `camion_status_enum` | DISPONIBLE, EN_MISSION, MAINTENANCE, PANNE |
| `permis_type_enum` | B, C, CE, D |
| `chauffeur_status_enum` | ACTIF, CONGE, ARRET_MALADIE, INACTIF |
| `statut_demande_enum` | NOUVELLE, PLANIFIEE, EN_COURS, LIVREE, ANNULEE |
| `priorite_enum` | NORMALE, HAUTE, URGENTE |
| `statut_plan_enum` | DRAFT, EN_REVUE, VALIDE, EXECUTE, CLOTURE |
| `periode_enum` | JOUR, SEMAINE, MOIS |
| `statut_mission_enum` | PLANIFIEE, EN_COURS, TERMINEE, ANNULEE |
| `mode_mission_enum` | NORMAL, PREMIUM |
| `evenement_type_enum` | PANNE_VEHICULE, RETARD_TRAFIC, CLIENT_INDISPONIBLE, DEPASSEMENT_CAPACITE, DEMANDE_LAST_MINUTE, CLIENT_COMPLAINT |
| `kpi_frequence_enum` | daily, weekly, monthly, yearly |
| `kpi_direction_enum` | UP, DOWN |
| `kpi_status_enum` | OK, WARN, ALERT, NA |
