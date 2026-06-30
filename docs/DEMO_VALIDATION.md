# Coficab implementation validation

## One-time database change

Apply the R4-13 unit migration before recomputing historical KPI snapshots:

```powershell
psql -U postgres -d coficab_db -f database/migration_kpi_fuel_units.sql
psql -U postgres -d coficab_db -f database/migration_driver_integrity.sql
psql -U postgres -d coficab_db -f database/migration_rental_approval.sql
python backend/scripts/recompute_kpis.py --from 2026-01-01 --to 2026-06-19
```

R4-13 is displayed in `mL/T.km`; its target and bands are therefore stored as
`140 / 160 / 180`, not the source `0.14 / 0.16 / 0.18 L/T.km` values.

The carbon conversion factor is explicit configuration:

```env
DIESEL_CO2E_KG_PER_L=2.68
CARBON_FACTOR_SOURCE=replace-with-approved-source
CARBON_FACTOR_BOUNDARY=replace-with-approved-boundary
CARBON_FACTOR_EFFECTIVE_FROM=YYYY-MM-DD
APP_ENV=development
DEV_AUTH_BYPASS=1
JWT_SECRET=replace-with-a-long-random-secret
TFM_INGEST_API_KEY=replace-with-a-secret-provider-key
```

Replace it with Coficab's approved factor before using carbon figures in an
official report.

Set `APP_ENV=production` and `DEV_AUTH_BYPASS=0` outside local demonstrations;
the frontend will attach the bearer token stored as `access_token`.

## Delay simulation

1. Start the backend and frontend.
2. Ensure at least one mission is `EN_COURS`, with a pending stop
   whose client has latitude and longitude.
3. Open `/map`.
4. Click **Simulate 25-minute delay**.
5. Confirm the marker popup says `Source: MAP_SIMULATION`.
6. Open `/ai-monitor` and confirm exactly one unresolved delay alert appears.
7. Repeat the simulation and confirm a duplicate incident is not created within
   the two-hour deduplication window.

Production TFM samples use `POST /api/tracking/tfm/sync` with an `X-TFM-Key`
header matching `TFM_INGEST_API_KEY`, a
`mission_id`, and numeric `delay_minutes`. Delays over 15 minutes create the
same deduplicated incident flow while retaining `TFM` as their source.

## Screenshot evidence for Manal

- Dashboard showing the ISO week and distance in kilometres.
- Corrected fuel KPI and its `mL/T.km` unit.
- Carbon history and configured factor.
- Driver roster before and after adding a driver.
- Generated plan with an AI rental recommendation.
- Rental approval followed by the regenerated plan.
- Map before the simulated delay.
- Map delayed marker with `MAP_SIMULATION` source visible.
- AI Monitor showing the delay incident.
- Resolved incident or replanning result.

## Automated verification

```powershell
cd backend
python -m pytest -q

cd ../frontend
npm run build
```
