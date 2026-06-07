---
name: implement-osrm-routing
description: Implement OSRM-backed road routing in a logistics planning codebase, especially the Coficab platform, when distance, ETA, itinerary, generated planning, VRPTW, OR-Tools, depot-client-client-depot routing, route geometry, route legs, or hardcoded/haversine delivery calculations need to be replaced with self-hosted OSRM using real database client/depot coordinates.
---

# Implement OSRM Routing

## Goal

Replace approximate delivery distance and ETA calculations with self-hosted OSRM road routing while keeping OR-Tools as the planner/optimizer unless the user explicitly asks to migrate to VROOM.

Use OSRM for routing truth:
- `/table/v1/driving` for duration and distance matrices.
- `/route/v1/driving` for final route geometry, ordered legs, total distance, total duration, and turn-by-turn steps.
- `/nearest/v1/driving` when coordinates need road snapping validation.

Use OR-Tools for planning logic:
- capacity constraints,
- time windows,
- palette handling durations,
- vehicle assignment,
- stop ordering when the project already uses OR-Tools.

## Workflow

1. Audit current calculations.
   - Search for `haversine`, `distance`, `duration`, `eta`, `arrival_time`, `departure_time`, `speed`, `km`, `getClientPosition`, and hardcoded depot constants.
   - Identify every UI field displaying distance, ETA, travel minutes, trip duration, route cost, and itinerary.
   - In the Coficab project, inspect `frontend/app/generated-planning/page.jsx`, `frontend/app/generated-daily-planning/page.jsx`, `frontend/data/coficabData.js`, `backend/app/services/vrptw_optimizer.py`, `backend/app/services/daily_plan_builder.py`, `backend/app/services/geo_service.py`, and `backend/app/routes/optimization.py`.

2. Confirm the data contract before implementing.
   - Read `references/project-contract.md`.
   - Do not proceed with production-accurate routing until depot coordinates and client coordinates/addresses are available from the database or an authoritative import.
   - If data is incomplete, implement clear validation errors and unassigned reasons instead of fake coordinates.

3. Add an OSRM provider/service layer.
   - Centralize OSRM calls in a backend service such as `osrm_service.py`.
   - Make the base URL configurable through environment variables, for example `OSRM_BASE_URL=http://osrm:5000`.
   - Return normalized units: meters, kilometers, seconds, minutes.
   - Cache matrix and route responses by coordinate sequence plus profile/version where appropriate.
   - Fail closed: if OSRM cannot route a stop, mark it unrouteable with a reason; do not fall back silently to straight-line distance for final displayed numbers.

4. Build a road matrix for OR-Tools.
   - Collect node 0 as the depot and nodes 1..N as routable deliveries.
   - Call OSRM table with `annotations=duration,distance`.
   - Feed OR-Tools integer durations in minutes or seconds.
   - Use OSRM distances for distance cost when needed.
   - Keep service time separate from travel time.
   - Model palette handling as 5 minutes per palette/position for loading/unloading unless a delivery-specific override exists.
   - Treat Excel `ETD`/`ETA` as a soft requested delivery slot in this project, not as a hard time window, unless a separate hard constraint is provided.

5. Group deliveries by road-route synergy, not just geographic closeness.
   - Do not rely on latitude/longitude clustering alone.
   - Use OSRM matrix distances/durations to evaluate insertion cost and route savings.
   - Prefer grouping stops when the combined depot-stop-stop-depot route is close to the natural corridor or return path for that truck.
   - Example target behavior: Sousse and Mahdia can share a truck because Sousse is on the way to Mahdia; Kairouan can be inserted on the return itinerary if OSRM shows it is a reasonable alternative path back to the depot; Jendouba should usually remain on another truck because it is in the opposite direction.
   - Keep capacity, weight, vehicle availability, requested-slot penalties, and hard constraints above corridor savings.

6. Generate final itinerary after optimization.
   - After OR-Tools returns the ordered stops for each truck, call OSRM route with the exact ordered sequence:
     `depot -> stop1 -> stop2 -> ... -> depot`.
   - Request `steps=true`, `geometries=geojson`, `overview=full`, and `annotations=duration,distance`.
   - Store or return route-level totals, per-leg totals, geometry, and maneuver steps.
   - Derive UI ETAs from per-leg OSRM durations plus waiting and service time.

7. Update frontend behavior.
   - Remove frontend coordinate guessing and fake fallback coordinates.
   - Display backend route totals and per-leg values.
   - When dispatchers drag/drop/add/resize stops, call a backend recalculate endpoint that reruns OSRM for the changed sequence instead of reflowing all timing locally.
   - If manual edits intentionally override computed times, label them as manual and keep the last computed OSRM values separately.

8. Validate.
   - Unit test OSRM response normalization with mocked route/table responses.
   - Integration test planning with a tiny fixture: depot plus 2-3 clients.
   - Verify no displayed distance/ETA comes from hardcoded values, frontend fabricated coordinates, or haversine fallback.
   - Compare one known route manually against OSRM output and confirm UI totals equal the sum of OSRM legs plus service/waiting rules.
   - Add a fixture like Sousse/Mahdia/Kairouan/Jendouba and assert the road-synergy grouping prefers the east/central corridor together and separates the northwest route when capacity allows.

## Coficab-Specific Notes

Prefer changing the newer daily planning path first, because `DailyPlanBuilder` already separates location resolution, matrix creation, scheduling, and UI output.

Target replacements:
- Replace `DailyPlanBuilder._build_matrix` straight-line/client-directory hybrid logic with OSRM table output.
- Replace legacy `VRPTWOptimizer` haversine `_dist` and `_build_dist_matrix` paths if the `Generated Planning` page remains in use.
- Remove or bypass `getClientPosition` from generated planning payload construction.
- Replace hardcoded `/api/optimization/route` placeholder values before exposing that endpoint as real route optimization.
- Change `PlanningService.parse_constraints` / `DailyPlanBuilder` behavior so Excel `ETD`/`ETA` are modeled as preferred-slot metadata or a soft penalty, not `constraints.time_window`.
- Replace coordinate-only `cluster_zones`/`capacity_aware_cluster` assignment for OSRM planning with road-matrix route-savings or insertion-cost grouping so same-corridor and return-path deliveries can share a truck.
- Replace current `DailyPlanConfig.service_minutes=20` and `service_minutes_per_position=3.0` behavior with the business rule of 5 minutes per palette/position for handling, unless later data provides a different per-client override.

Keep the existing OR-Tools dependency unless the user asks for VROOM. VROOM is a good future option for multi-vehicle optimization, but it is not necessary to fix ETA/distance accuracy.

## References

- Load `references/project-contract.md` before implementation.
- OSRM docs: https://project-osrm.org/docs/
- OSRM API details: https://project-osrm.org/docs/v5.24.0/api/
