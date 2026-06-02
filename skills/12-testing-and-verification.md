# 12 — Testing & Verification

> Goal: every feature has a deterministic way to prove it works. Tests are organized by KPI, not by file — so when R4-13 looks wrong on the dashboard, you know exactly which test to run.

## Current implementation status

Done:
- Backend pytest coverage exists for auth/security, ingestion service and API, optimizer/watchdog paths, plan validation, dispatch, incidents, monitoring, KPI jobs, and generated daily planning.
- `backend/tests/test_kpi_invariants.py` pins the current live KPI formulas and color bands for all eight Coficab KPI codes.
- `.github/workflows/ci.yml` runs backend tests and a KPI-focused slice including `test_kpi_invariants.py`.

Pending:
- The full ingestion -> optimize -> validate -> delivered -> KPI snapshot integration test is still pending.
- Manual UI verification is still pending, especially frontend auth guards and admin ingestion/log pages.

## Test pyramid

| Layer | Tool | Where | What |
|---|---|---|---|
| Unit | `pytest` | `backend/tests/unit/` | KPI formulas, validation rules, parsers |
| Integration | `pytest` + `TestClient` | `backend/tests/integration/` | API endpoints, DB round-trip |
| End-to-end | manual (browser) | `frontend/` | Visual: dashboard matches DB |

Skip Cypress/Playwright for v1. Manual verification on the UI is fine for the scope.

---

## Fixtures: deterministic data set

`backend/tests/fixtures.py`:

```python
from datetime import date, datetime, timedelta
from app.models import (Camion, CamionStatus, Chauffeur, ChauffeurStatus,
                        Client, DemandeLocal, PlanVersion, PlanMission,
                        MissionDemande, EvenementAlea, StatutPlan, StatutMission,
                        StatutDemande, Priorite, Periode, EvenementType)

def seed_minimal(db):
    """Return ids for: 2 trucks, 2 drivers, 3 clients, 5 demandes."""
    t1 = Camion(plate_number="TR-01", type="SEMI", capacite_kg=24000, max_palettes=33,
                status=CamionStatus.DISPONIBLE)
    t2 = Camion(plate_number="TR-02", type="PORTEUR", capacite_kg=12000, max_palettes=18,
                status=CamionStatus.DISPONIBLE)
    db.add_all([t1, t2]); db.flush()

    d1 = Chauffeur(id=1, full_name="Ali Driver", phone="+212600000001",
                   permis_type="CE", status=ChauffeurStatus.ACTIF, camion_defaut_id=t1.id)
    d2 = Chauffeur(id=2, full_name="Hassan Driver", phone="+212600000002",
                   permis_type="CE", status=ChauffeurStatus.ACTIF, camion_defaut_id=t2.id)
    db.add_all([d1, d2]); db.flush()

    c1 = Client(id=100, nom="SOMACO",   city="Casablanca", latitude=33.5731, longitude=-7.5898,
                fenetre_ouverture="08:00", fenetre_fermeture="18:00")
    c2 = Client(id=101, nom="TANGITEX", city="Tangier",     latitude=35.7595, longitude=-5.8340,
                fenetre_ouverture="09:00", fenetre_fermeture="17:00")
    c3 = Client(id=102, nom="RABAUTO",  city="Rabat",       latitude=34.0209, longitude=-6.8416,
                fenetre_ouverture="08:30", fenetre_fermeture="16:30")
    db.add_all([c1, c2, c3]); db.flush()

    today = date.today()
    demandes = [
        DemandeLocal(client_id=100, quantite_kg=8000, nombre_palettes=10,
                     date_livraison=today, priorite=Priorite.NORMALE, statut=StatutDemande.NOUVELLE),
        DemandeLocal(client_id=101, quantite_kg=4500, nombre_palettes=6,
                     date_livraison=today, priorite=Priorite.HAUTE,  statut=StatutDemande.NOUVELLE),
        DemandeLocal(client_id=102, quantite_kg=2000, nombre_palettes=3,
                     date_livraison=today, priorite=Priorite.NORMALE, statut=StatutDemande.NOUVELLE),
        DemandeLocal(client_id=100, quantite_kg=1500, nombre_palettes=2,
                     date_livraison=today, priorite=Priorite.URGENTE, statut=StatutDemande.NOUVELLE),
        DemandeLocal(client_id=101, quantite_kg=6000, nombre_palettes=8,
                     date_livraison=today, priorite=Priorite.NORMALE, statut=StatutDemande.NOUVELLE),
    ]
    db.add_all(demandes); db.flush()
    db.commit()
    return {"trucks": [t1.id, t2.id], "drivers": [1, 2],
            "clients": [100, 101, 102], "demandes": [d.id for d in demandes]}
```

---

## KPI-anchored test cases

One test per KPI. If all 8 pass, the platform "works" by Coficab's own definition.

### `backend/tests/unit/test_kpi_otif.py` (R4-06)

```python
from datetime import date, datetime, timedelta
from app.services.kpi_service import KpiService

def test_otif_perfect(db, fixtures):
    # 5 demandes, all on time & in full → 100%
    today = date.today()
    for did in fixtures["demandes"]:
        d = db.get(DemandeLocal, did)
        d.statut = StatutDemande.LIVREE
        d.livree_a_temps = True
        d.quantite_livree_kg = d.quantite_kg
    db.commit()
    r = KpiService(db).compute_otif(today)
    assert r.value == 100.0
    assert r.color == "green"

def test_otif_two_late(db, fixtures):
    today = date.today()
    rows = [db.get(DemandeLocal, did) for did in fixtures["demandes"]]
    for d in rows:
        d.statut = StatutDemande.LIVREE
        d.quantite_livree_kg = d.quantite_kg
        d.livree_a_temps = True
    rows[0].livree_a_temps = False
    rows[1].livree_a_temps = False
    db.commit()
    r = KpiService(db).compute_otif(today)
    assert r.value == 60.0
    assert r.color == "red"   # < 92%
```

### `test_kpi_otd.py` (R4-02)
Same shape: quantity-weighted, not row-weighted. Test that 4500 kg on-time + 8000 kg late + 1500 kg on-time gives `OTD = 6000/14000 ≈ 42.86%` → red.

### `test_kpi_fuel.py` (R4-13)
Insert a mission with `km=100, charge_kg=10_000 (=10T), fuel_consomme_l=15`. Expected: `15 × 1000 / (10 × 100) = 15 mL/T.km`. (The spec's target is 0.14, units must match — if the test number sits in a different order of magnitude, your tonnage unit is wrong.)

### `test_kpi_logistics_cost.py` (R5-10)
Insert one mission: `cout_consommables_eur=50, cout_emballage_eur=30, cout_transport_eur=200, charge_kg=10_000`. Expected: `(50+30+200)/10 = 28 €/T` → red.

### `test_kpi_load_efficiency.py` (R4)
Truck `capacite_kg=10_000`, `max_palettes=20`. Mission with `charge_kg=8000, charge_palettes=10`. Expected: `max(80%, 50%) = 80%` → green (if threshold is 80).

### `test_kpi_premium_freight.py` (R4-02-PF, R4-03)
Three missions: 2 normal, 1 with `mode='PREMIUM', cout_premium_eur=3000`. Expected count=1 (green), cost=3000 (yellow).

### `test_kpi_customer_incidents.py` (R4-12)
Insert 5 incidents with `type='CLIENT_COMPLAINT'` in May 2026. Sum of `km_parcourus` across May missions = 250_000 km. Expected: `5/250_000 × 1_000_000 = 20` → red (> 15).

---

## Integration tests

`backend/tests/integration/test_end_to_end.py`:

```python
def test_full_planning_cycle(client, fixtures):
    """Ingestion → optimize → validate → KPI snapshot."""
    # 1. demandes already in fixtures; skip ingestion.
    # 2. Run optimizer
    r = client.post("/api/optimization/run", json={"day": str(date.today())})
    assert r.status_code == 200
    plan_id = r.json()["plan_version_id"]

    # 3. Preview impact
    r = client.get(f"/api/planning/{plan_id}/impact")
    assert r.status_code == 200
    impact = r.json()
    assert impact["load_efficiency_pct"] > 0

    # 4. Validate
    r = client.post(f"/api/planning/{plan_id}/validate",
                    headers={"Authorization": "Bearer <planner-token>"})
    assert r.status_code == 200

    # 5. Mark every stop delivered
    plan = client.get(f"/api/planning/{plan_id}").json()
    for mission in plan["missions"]:
        for stop in mission["stops"]:
            client.post(f"/api/tracking/stops/{stop['id']}/delivered",
                        json={"quantite_livree_kg": stop["quantite_kg"]})

    # 6. Run KPI job
    from app.agents.kpi_jobs import run_daily
    run_daily(date.today())

    # 7. Read KPIs
    r = client.get("/api/metrics/kpi")
    kpis = {k["code"]: k for k in r.json()["kpis"]}
    assert kpis["R4-06"]["value"] > 0
    assert kpis["R4-02"]["value"] > 0
```

---

## Manual UI verification checklist

After every backend change that touches a KPI, walk through this in the browser:

- [ ] `/dashboard` loads with no console errors.
- [ ] All 5 (or more) KPI tiles show a value (not "—"), correct unit, correct color band.
- [ ] Sparkline / trend arrows render.
- [ ] `/planning` shows the latest DRAFT or VALIDE plan.
- [ ] Drag a stop between trucks → impact panel updates within 1 s.
- [ ] Validate the plan → toast confirmation, plan status flips to VALIDE.
- [ ] `/ai-monitor` shows the dispatch attempts (mock or real).
- [ ] `/admin` ingestion logs page shows last 20 import attempts.
- [ ] Logout → `/dashboard` redirects to `/login` (or shows the auth wall).
- [ ] No visual regression vs the pre-API screenshots (colors, spacing, icons).

---

## CI hook (optional, recommended)

`.github/workflows/test.yml` (or local script `make test`):

```yaml
- run: pip install -r backend/requirements.txt
- run: pytest backend/tests/ -v --tb=short
- run: npm --prefix frontend ci
- run: npm --prefix frontend run build
```

Build must pass with zero TypeScript errors. SWR types are inferred; the new hooks must have explicit return types.

---

## Anti-patterns

- ❌ Snapshot tests on JSX. Layout is locked but inner text changes (KPI values). Snapshots will fail constantly.
- ❌ Mocking the DB. Tests run against a throwaway Postgres (dockerized in CI, local for dev).
- ❌ Time-based flakiness. Use `freezegun` or a `clock` injected dep for tests touching dates.
- ❌ Sharing state between tests. Each test function gets a fresh transaction, rolled back at teardown.

---

## Where to start

1. Wire one fixture, one KPI test (R4-06 OTIF). Get it green.
2. Add a test per KPI (8 total).
3. Add the integration test once routes for `/run`, `/validate`, `/delivered` exist.
4. Manual UI walk-through after every backend deploy.

If at any point a KPI's value on the dashboard doesn't match the test fixture's expected value, **the formula in `KpiService` is the source of truth — fix the test or the formula, then the UI follows automatically.**
