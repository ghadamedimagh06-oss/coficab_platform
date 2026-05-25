# Reference — KPI Formulas

Quick lookup. All formulas come from the Coficab monthly performance report.

---

## R4-06 — OTIF (On-Time In-Full)
- **Unit:** %
- **Direction:** higher is better
- **Target 2025:** 96%
- **Bands:** green ≥ 94 • yellow 92–94 • red < 92

```
OTIF = COUNT(demandes where livree_a_temps = TRUE AND quantite_livree = quantite_demandee)
     / COUNT(demandes total)
     × 100
```

---

## R4-02 — OTD (On-Time Delivery)
- **Unit:** %
- **Direction:** higher is better
- **Target 2025:** 96%
- **Bands:** green ≥ 94 • yellow 92–94 • red < 92

```
OTD = SUM(quantite_livree_kg where livree_a_temps = TRUE)
    / SUM(quantite_livree_kg total)
    × 100
```

Quantity-weighted (per the spec: "Total quantity delivered on time / Total quantity delivered of all the orders").

---

## R4-02-PF — Premium Freight Cost
- **Unit:** EUR
- **Direction:** lower is better
- **Target 2025:** 1 500
- **Bands:** green ≤ 2 500 • yellow 2 500–3 500 • red > 3 500

```
Premium Freight Cost = SUM(plan_mission.cout_premium_eur WHERE mode = 'PREMIUM')
```

Aggregated per month.

---

## R4-03 — Premium Freight Occurrences
- **Unit:** Nb
- **Direction:** lower is better
- **Target 2025:** 1
- **Bands:** green ≤ 3 • yellow 3–5 • red > 5

```
Premium Freight Occurrences = COUNT(plan_mission WHERE mode = 'PREMIUM')
```

Aggregated per month.

---

## R4-13 — Fuel Consumption Efficiency
- **Unit:** mL/T.km
- **Direction:** lower is better
- **Target 2025:** 0.14
- **Bands:** green ≤ 0.16 • yellow 0.16–0.18 • red > 0.18

Inputs:
- (32) Fuel consumption — `SUM(plan_mission.fuel_consomme_l)`  in litres
- (33) Tonnage transported — `SUM(plan_mission.charge_kg) / 1000`  in tonnes
- (34) Kilometres travelled — `SUM(plan_mission.km_parcourus)`  in km

```
Fuel per tonnage transported = (32 × 1000) / (33 × 34)   [mL / T.km]   ← R4-13
Fuel per 100 km              = (32) / ((34) / 100)        [L / 100km]
Return-empty-km rate         = (35) / (34)                [%]
```
where (35) = `SUM(plan_mission.km_a_vide)`.

---

## R5-10 — Logistics Cost
- **Unit:** €/T
- **Direction:** lower is better
- **Target 2025:** 16
- **Bands:** green ≤ 18 • yellow 18–20 • red > 20

```
Logistics Cost = ( (27) + (28) + (29) ) / (30)
```
- (27) Logistics consumables (incl. Fuel Fenwick) — `SUM(plan_mission.cout_consommables_eur)`
- (28) Packaging — `SUM(plan_mission.cout_emballage_eur)`
- (29) Transportation (premium freight + reparation + fuel camion + déplacement) — `SUM(plan_mission.cout_transport_eur)`
- (30) Vente en tonne — `SUM(plan_mission.charge_kg) / 1000`

Aggregated monthly.

---

## R4-12 — Customer Logistics Incidents per MKm sold
- **Unit:** Nb
- **Direction:** lower is better
- **Target 2025:** 13
- **Bands:** green ≤ 14 • yellow 14–15 • red > 15

```
Customer Logistics Incidents / MKm = (32) / (33) × 1 000 000
```
- (32) = `COUNT(evenement_alea WHERE type = 'CLIENT_COMPLAINT')`
- (33) = `SUM(plan_mission.km_parcourus)`  (total km sold in the period)

---

## R4 — Load Efficiency Rate
- **Unit:** %
- **Direction:** higher is better
- **Target 2025:** (TBD with business — placeholder 85%)
- **Bands:** green ≥ target • yellow between bands • red below

Per mission:
```
Load(Plts %)         = (plan_mission.charge_palettes / camion.max_palettes) × 100
Load(Kg %)           = (plan_mission.charge_kg       / camion.capacite_kg)  × 100
Load Efficiency (%)  = MAX(Load(Plts), Load(Kg))
```

Per day/month: average across all missions.

---

## How values feed the bands

```python
def color(definition, value):
    if definition.direction == "UP":     # OTIF, OTD, Load Eff
        if value >= definition.green_min:  return "green"
        if value >= definition.yellow_min: return "yellow"
        return "red"
    # DOWN: Fuel, Cost, Incidents, Premium
    if value <= definition.green_max:  return "green"
    if value <= definition.yellow_max: return "yellow"
    return "red"
```

This is the single function every KPI passes through. Don't duplicate it.
