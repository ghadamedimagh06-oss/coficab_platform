# 01 — Scoring System (THE Anchor)

> **This is the source of truth for every decision the platform makes.** Every other skill exists to feed or consume one of these KPIs. If a feature doesn't move a KPI, it doesn't ship.

The Coficab monthly performance report tracks 8 official indicators. The platform must compute, store, and display **each one exactly as the report defines it** — same formula, same unit, same color band, same target.

---

## 1. The 8 official indicators

| Code       | Indicator                                | Unit    | Target 2025 | Green band | Yellow band     | Red band |
|------------|-------------------------------------------|---------|-------------|------------|-----------------|----------|
| R4-06      | OTIF — On-Time In-Full                    | %       | 96%         | ≥ 94%      | 92% to 94%      | < 92%    |
| R4-02      | OTD — On-Time Delivery                    | %       | 96%         | ≥ 94%      | 92% to 94%      | < 92%    |
| R4-02-PF ¹ | Premium Freight cost (Extra Transport)    | EUR     | 1 500       | ≤ 2 500    | 2 500 to 3 500  | > 3 500  |
| R4-03      | Number of Premium Freight occurrences     | Nb      | 1           | ≤ 3        | 3 to 5          | > 5      |
| R4-13      | Fuel Consumption Efficiency               | mL/T.km | 0.14        | ≤ 0.16     | 0.16 to 0.18    | > 0.18   |
| R5-10      | Logistics cost                            | €/T     | 16          | ≤ 18       | 18 to 20        | > 20     |
| R4-12      | Customer logistics incidents per MKm sold | Nb      | 13          | ≤ 14       | 14 to 15        | > 15     |
| R4         | Load Efficiency Rate                      | %       | (target tbd)| ≥ target   | between bands   | < min    |

> ¹ **R4-02-PF** is the platform's internal code for Premium Freight Cost. The Coficab monthly report labels it R4-02 in the printed column header, but since R4-02 already uniquely identifies OTD (a different unit and direction), using the same code in `kpi_definition` would corrupt the catalog. R4-02-PF is used everywhere in the codebase and seed SQL. Never conflate the two.

The dashboard's "Follow-up" column shows the cell colored according to the band. The KPI engine must compute both the **value** and the **color** for every snapshot.

---

## 2. Formulas (verbatim from the spec)

### R4-06 — OTIF
```
OTIF = (deliveries on time AND in full) / (total deliveries) × 100
```
Where:
- on time = `plan_mission.heure_sortie_reelle ≤ heure_sortie_prevue + tolerance_min` AND arrival within client window
- in full = `demandes_local.quantite_kg_livree == quantite_kg_demandee`

### R4-02 — OTD
```
OTD = quantity delivered on time / total quantity delivered, all orders × 100
```
Spec note (verbatim): *"Total quantity delivered on time / Total quantity delivered of all the orders"*.

### R4-02 / R4-03 — Premium Freight (Extra Transport)
- Premium Freight cost (EUR) = sum of `plan_mission.cout_premium_eur` for missions flagged `mode = 'PREMIUM'`.
- Number of occurrences = count of those missions.
A mission is premium when it was booked outside the normal weekly plan (last-minute, express, dedicated transport).

### R4-13 — Fuel Consumption Efficiency
The platform stores three raw aggregates per period:
- (32) `fuel_consomme_l` — fuel consumed in litres
- (33) `tonnage_transporte_kg` — tonnage transported in kg
- (34) `km_parcourus` — kilometres travelled

```
Fuel per tonnage transported  = (32 × 1000) / (33 × 34)        [mL / T.km]   ← R4-13
Fuel per 100 km                = (32) / ((34) / 100)            [L / 100km]
Return-empty-km rate           = (35) / (34)                    [%]
```
Where (35) = `km_a_vide` (kilometres run empty).

### R5-10 — Logistics Cost (€/T)
```
Logistics Cost = ( (27) + (28) + (29) ) / (30)
```
- (27) Logistics consumables (incl. Fuel Fenwick) — `SUM(plan_mission.cout_consommables_eur)`
- (28) Packaging — `SUM(plan_mission.cout_emballage_eur)`
- (29) Transportation costs = premium freight + reparation + fuel camion + déplacement — `SUM(plan_mission.cout_transport_eur)`
- (30) Vente en tonne — `SUM(plan_mission.charge_kg) / 1000` in tonnes

> ⚠️ **v1 proxy.** The spec expects "tonnes sold" (a commercial volume figure from ERP/sales). Because no sales system is integrated in v1, the platform uses **transported tonnage** (`charge_kg / 1000`) as a proxy — directionally correct for internal benchmarking. If the business requires exact cost-per-tonne-sold, wire a monthly sales input via `POST /api/metrics/monthly-sales` and replace this field with the imported value.

### R4-12 — Customer Logistics Incidents / MKm sold

> ⚠️ **Naming collision warning.** The spec report uses positional numbers (32), (33) for *multiple* KPIs — fuel and incidents reuse the same ordinals with different meanings. All formulas below use explicit field names instead to prevent implementation errors.

```
Customer Logistics Incidents per MKm sold =
    COUNT(evenement_alea WHERE type = 'CLIENT_COMPLAINT')
    / SUM(plan_mission.km_parcourus)
    × 1 000 000
```

Fields:
- `nb_incidents` = `COUNT(evenement_alea WHERE type = 'CLIENT_COMPLAINT')` for the period
- `km_parcourus` = `SUM(plan_mission.km_parcourus)` for the period (total km operated = km sold proxy)

### R4 — Load Efficiency Rate
The spec defines three sub-metrics; the headline R4 = `max(Load(Pallets %), Load(Kg %))`.
```
Load(Plts %) = total_pallets_used   / max_pallets_capacity   × 100
Load(Kg %)   = total_weight_loaded  / max_kg_capacity        × 100
Load Efficiency (%) = max( Load(Kg), Load(Plts) )
```
Computed per trip → averaged per day → averaged per month.

---

## 3. How each indicator is fed by the system

| KPI | Fed by | When |
|---|---|---|
| OTIF | `plan_mission` completion + `demandes_local.quantite_kg_livree` | Driver/dispatch confirms delivery |
| OTD | `plan_mission.heure_arrivee_reelle` vs `demande.heure_arrivee_souhaitee` | On delivery confirmation |
| Premium Freight cost | `plan_mission.cout_premium_eur` when `mode='PREMIUM'` | Plan creation |
| Premium Freight occurrences | count of `plan_mission` where `mode='PREMIUM'` | Plan creation |
| Fuel Consumption Efficiency | `plan_mission.fuel_consomme_l`, `tonnage`, `km` | Mission close-out |
| Logistics Cost | `plan_mission.cout_*_eur` + `vente_tonnes` (manual or imported) | KPI job, monthly |
| Customer Logistics Incidents/MKm | `evenement_alea` (`type='CLIENT_COMPLAINT'`) + `km_vendus` | Incident logged |
| Load Efficiency | `plan_mission.charge_kg / camion.capacite_kg` and palette equivalent | Plan creation + dispatch close-out |

---

## 4. Storage model

Three tables (full DDL in skill 02):

- `kpi_definition` — the catalog (one row per code: R4-06, R4-02, …). Holds unit, frequency, target, green/yellow/red thresholds. Seeded once.
- `kpi_journalier` — one row per (kpi_def_id, date_mesure). Daily snapshot. Holds the raw aggregates (qte_*, fuel_*, etc.) AND the computed value AND the color.
- `kpi_mensuel` — one row per (kpi_def_id, annee, mois). Monthly aggregate. Holds value + target + status (`OK` / `WARN` / `ALERT`).

The **color** field is computed at write time, not at read time. This means the frontend never re-derives bands — it just reads `kpi_mensuel.status` and renders.

---

## 5. Reference implementation — `KpiService`

> **This snippet is a design reference, not the source of truth.**
> The authoritative implementation lives in `backend/app/services/kpi_service.py`.
> If the file and this snippet disagree, **the file wins**. Update this section when the spec formula changes.

`backend/app/services/kpi_service.py`:

```python
from dataclasses import dataclass
from datetime import date
from sqlalchemy.orm import Session
from app.models.kpi import KpiDefinition, KpiJournalier, KpiMensuel
from app.models.plan import PlanMission
from app.models.demande import DemandeLocal
from app.models.evenement import EvenementAlea

@dataclass
class KpiResult:
    code: str
    value: float
    unit: str
    color: str  # "green" | "yellow" | "red"

class KpiService:
    def __init__(self, db: Session):
        self.db = db

    # -----------------------------
    # Color band helper
    # -----------------------------
    def color_for(self, definition: KpiDefinition, value: float) -> str:
        # Higher-is-better KPIs (OTIF, OTD, Load Eff)
        if definition.direction == "UP":
            if value >= definition.green_min:   return "green"
            if value >= definition.yellow_min:  return "yellow"
            return "red"
        # Lower-is-better KPIs (Fuel, Cost, Incidents, Premium Freight)
        if value <= definition.green_max:       return "green"
        if value <= definition.yellow_max:      return "yellow"
        return "red"

    # -----------------------------
    # R4-06 OTIF
    # -----------------------------
    def compute_otif(self, day: date) -> KpiResult:
        q = self.db.query(DemandeLocal).filter(DemandeLocal.date_livraison == day)
        total = q.count()
        if total == 0:
            return self._zero("R4-06")
        on_time_in_full = q.filter(
            DemandeLocal.statut == "LIVREE",
            DemandeLocal.livree_a_temps == True,
            DemandeLocal.quantite_livree_kg == DemandeLocal.quantite_demandee_kg,
        ).count()
        value = round(on_time_in_full / total * 100, 2)
        return self._wrap("R4-06", value)

    # -----------------------------
    # R4-02 OTD
    # -----------------------------
    def compute_otd(self, day: date) -> KpiResult:
        rows = self.db.query(DemandeLocal).filter(DemandeLocal.date_livraison == day).all()
        total_qty = sum(r.quantite_livree_kg or 0 for r in rows)
        on_time_qty = sum(r.quantite_livree_kg or 0 for r in rows if r.livree_a_temps)
        if total_qty == 0:
            return self._zero("R4-02")
        return self._wrap("R4-02", round(on_time_qty / total_qty * 100, 2))

    # -----------------------------
    # R4-13 Fuel Efficiency (mL / T.km)
    # -----------------------------
    def compute_fuel_efficiency(self, day: date) -> KpiResult:
        missions = self.db.query(PlanMission).filter(PlanMission.date_mission == day).all()
        litres   = sum(m.fuel_consomme_l or 0 for m in missions)
        tonnage  = sum((m.charge_kg or 0) for m in missions)
        km       = sum(m.km_parcourus or 0 for m in missions)
        if tonnage == 0 or km == 0:
            return self._zero("R4-13")
        value = round(litres * 1000 / (tonnage / 1000 * km), 3)  # mL / T.km
        return self._wrap("R4-13", value)

    # -----------------------------
    # R5-10 Logistics Cost (€/T)
    # -----------------------------
    def compute_logistics_cost(self, month: date) -> KpiResult:
        # month = first day of the month
        rows = self.db.query(PlanMission).filter(
            PlanMission.date_mission >= month,
            PlanMission.date_mission < self._next_month(month)
        ).all()
        cost_27 = sum(r.cout_consommables_eur or 0 for r in rows)
        cost_28 = sum(r.cout_emballage_eur or 0 for r in rows)
        cost_29 = sum(r.cout_transport_eur or 0 for r in rows)
        tonnes  = sum((r.charge_kg or 0) for r in rows) / 1000
        if tonnes == 0:
            return self._zero("R5-10")
        return self._wrap("R5-10", round((cost_27 + cost_28 + cost_29) / tonnes, 2))

    # -----------------------------
    # R4-12 Customer Logistics Incidents / MKm sold
    # -----------------------------
    def compute_customer_incidents(self, month: date) -> KpiResult:
        incidents = self.db.query(EvenementAlea).filter(
            EvenementAlea.type == "CLIENT_COMPLAINT",
            EvenementAlea.date_evenement >= month,
            EvenementAlea.date_evenement < self._next_month(month),
        ).count()
        # km_parcourus is used as proxy for "km sold" — see section 2 vente note
        km_sold = sum(
            (m.km_parcourus or 0) for m in self.db.query(PlanMission).filter(
                PlanMission.date_mission >= month,
                PlanMission.date_mission < self._next_month(month),
            )
        )
        if km_sold == 0:
            return self._zero("R4-12")
        return self._wrap("R4-12", round(incidents / km_sold * 1_000_000, 2))

    # -----------------------------
    # R4 Load Efficiency
    # -----------------------------
    def compute_load_efficiency(self, day: date) -> KpiResult:
        missions = self.db.query(PlanMission).filter(
            PlanMission.date_mission == day,
            PlanMission.statut.in_(["EN_COURS", "TERMINEE"]),
        ).all()
        if not missions:
            return self._zero("R4")
        ratios = []
        for m in missions:
            kg_ratio  = (m.charge_kg or 0) / (m.camion.capacite_kg or 1) * 100
            plt_ratio = (m.charge_palettes or 0) / (m.camion.max_palettes or 1) * 100
            ratios.append(max(kg_ratio, plt_ratio))
        return self._wrap("R4", round(sum(ratios) / len(ratios), 2))

    # -----------------------------
    # Helpers
    # -----------------------------
    def _wrap(self, code: str, value: float) -> KpiResult:
        d = self.db.query(KpiDefinition).filter(KpiDefinition.code == code).first()
        return KpiResult(code=code, value=value, unit=d.unite, color=self.color_for(d, value))

    def _zero(self, code: str) -> KpiResult:
        d = self.db.query(KpiDefinition).filter(KpiDefinition.code == code).first()
        return KpiResult(code=code, value=0.0, unit=d.unite, color="grey")

    @staticmethod
    def _next_month(d: date) -> date:
        return date(d.year + (1 if d.month == 12 else 0), 1 if d.month == 12 else d.month + 1, 1)
```

This module is the only place these formulas live. Routes never re-derive them.

---

## 6. Seed data for `kpi_definition`

`database/seed_kpi_definitions.sql`:

```sql
INSERT INTO kpi_definition
  (code, nom, description, unite, frequence, direction, target_2025,
   green_min, yellow_min, green_max, yellow_max)
VALUES
  ('R4-06','OTIF','On-Time In-Full','%','daily','UP',96, 94, 92, NULL, NULL),
  ('R4-02','OTD','On-Time Delivery (quantity-weighted)','%','daily','UP',96, 94, 92, NULL, NULL),
  ('R4-02-PF','Premium Freight Cost','Extra transport cost','EUR','monthly','DOWN',1500, NULL, NULL, 2500, 3500),
  ('R4-03','Premium Freight Occurrences','Number of premium transports','Nb','monthly','DOWN',1, NULL, NULL, 3, 5),
  ('R4-13','Fuel Consumption Efficiency','Fuel per tonnage transported','mL/T.km','daily','DOWN',0.14, NULL, NULL, 0.16, 0.18),
  ('R5-10','Logistics Cost','Logistics cost per tonne sold','€/T','monthly','DOWN',16, NULL, NULL, 18, 20),
  ('R4-12','Customer Logistics Incidents','Per MKm sold','Nb','monthly','DOWN',13, NULL, NULL, 14, 15),
  ('R4','Load Efficiency Rate','max(load kg, load pallets)','%','daily','UP',85, 80, 75, NULL, NULL);
```

(Replace target/green/yellow values for R4 once the business confirms them — the spec image leaves the bands blank.)

---

## 7. How the optimizer uses these KPIs (preview)

Skill 04 explains in detail. Summary: the objective function is

```
minimize:  α · total_km
         + β · expected_delay_penalty           ← targets OTD / OTIF
         + γ · (100 − load_efficiency_%)        ← targets R4
         + δ · expected_premium_freight_eur     ← targets R4-02-PF
         + ε · expected_fuel_litres_per_tkm     ← targets R4-13
```

Each weight maps to a KPI. The transport manager can tune (α, β, γ, δ, ε) from the admin UI to bias the optimizer toward whichever indicator is hurting that month.

---

## 8. Anti-patterns (do NOT do)

- ❌ Computing KPIs in the frontend. (Frontend reads `kpi_journalier` / `kpi_mensuel`, period.)
- ❌ Computing KPIs ad-hoc in route handlers. (Always go through `KpiService`.)
- ❌ Storing only the value and re-deriving the color on the fly. (Store both, frozen at compute time.)
- ❌ Re-using the generic `OTIF = completed / total` heuristic currently in `routes/metrics.py`. (Replace with `KpiService.compute_otif`.)
- ❌ Skipping `kpi_definition` seed. (Without it, color bands are unknown and the dashboard renders grey.)

---

## 9. Verification

For each KPI:
1. Insert deterministic test data (skill 12 has fixtures).
2. Run the formula by hand against the data.
3. Compare with `KpiService.compute_*()` output.
4. Round-trip: query `/api/metrics/kpi?code=R4-06&period=monthly` and confirm the JSON matches.
5. Eyeball the dashboard cell: same value, same color.

If all five checks pass, you're done with this KPI. If any fails, the formula is wrong — fix `KpiService`, not the database row.
