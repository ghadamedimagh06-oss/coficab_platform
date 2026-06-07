# Project Contract For OSRM Routing

Use this reference when implementing OSRM-backed route distance, duration, ETA, and itinerary calculations in the Coficab logistics platform.

## Required Database Data

Do not trust frontend fallback coordinates or guessed city coordinates for final displayed routing numbers.

Required depot fields:
- depot id/name
- depot full address
- depot latitude
- depot longitude
- optional depot open/close time

Required client fields:
- stable client id
- client name matching delivery rows
- delivery site full address
- city/country
- latitude
- longitude
- optional opening and closing time window
- optional unloading rules or access notes

Required delivery/order fields:
- delivery id or workbook row id
- client id
- delivery date
- quantity positions/pallets
- gross weight kg
- requested slot from Excel `ETD`/`ETA`, treated as soft/preferred in this project
- hard time window, only if provided separately from Excel `ETD`/`ETA`
- fixed truck or driver constraint, if any
- handling duration override, if any; otherwise use 5 minutes per palette/position

Required vehicle fields:
- truck id and label
- capacity positions/pallets
- capacity kg
- availability status
- optional start depot and end depot
- optional max shift/window
- optional profile constraints if later using truck-specific routing

## OSRM Deployment Assumptions

Use a self-hosted OSRM container or service built from an OpenStreetMap `.osm.pbf` extract that covers all delivery points. For the current project, Tunisia coverage is expected.

Expected environment:
- `OSRM_BASE_URL`, for example `http://osrm:5000`
- `OSRM_PROFILE`, usually `driving`
- map extract update procedure documented outside the skill

The application should support these OSRM calls:
- `GET /nearest/v1/driving/{lon},{lat}`
- `GET /table/v1/driving/{lon1},{lat1};{lon2},{lat2};...?annotations=duration,distance`
- `GET /route/v1/driving/{lon1},{lat1};{lon2},{lat2};...?steps=true&geometries=geojson&overview=full&annotations=duration,distance`

Coordinate order in OSRM URLs is `lon,lat`, not `lat,lon`.

## Backend Output Contract

For each generated plan, return route data that the UI can display without recomputing distance or time:

```json
{
  "routes": [
    {
      "truck_id": "Truck 1",
      "total_distance_km": 182.4,
      "total_travel_min": 214,
      "total_service_min": 75,
      "total_duration_min": 289,
      "geometry": { "type": "LineString", "coordinates": [] },
      "legs": [
        {
          "from": "Depot",
          "to": "Client A",
          "distance_km": 42.1,
          "travel_min": 51,
          "arrival_time": "08:51",
          "departure_time": "09:16",
          "service_min": 25,
          "steps": []
        }
      ]
    }
  ]
}
```

Keep route travel time separate from service time and waiting time:
- `travel_min`: OSRM leg duration only.
- `service_min`: delivery-site handling time, defaulting to `palette_count * 5 minutes`.
- `depot_load_min`: depot loading time if modeled separately, defaulting to `loaded_palette_count * 5 minutes`.
- `waiting_min`: time spent waiting for a true hard time window, if one exists.
- `requested_slot`: Excel `ETD`/`ETA`; use it as a soft preference/penalty, not a hard constraint.
- `eta` or `arrival_time`: prior departure plus OSRM travel plus any necessary waiting.
- `departure_time`: arrival plus service.

## Implementation Pattern

1. Resolve delivery locations from DB.
2. Validate coordinates and snap/check them with OSRM nearest if needed.
3. Build a matrix:
   - node 0 depot
   - nodes 1..N deliveries
   - duration matrix from OSRM
   - distance matrix from OSRM
4. Solve the plan with OR-Tools:
   - objective can combine travel duration and distance
   - capacity constraints from truck fields
   - hard time windows only from explicit hard constraints, not Excel `ETD`/`ETA`
   - soft penalty for deviating from the Excel requested slot
   - handling duration added in transit callback, using 5 minutes per palette/position by default
5. For each ordered truck route, call OSRM route and attach itinerary data.
6. Store or return the itinerary so frontend does not fabricate values.

## Road-Synergy Grouping Requirement

The planner must group deliveries by actual OSRM road-route synergy, not only by geographic distance or angle from depot.

Target behavior:
- If Sousse is naturally on the road to Mahdia, group Sousse and Mahdia on the same truck when capacity, weight, availability, requested slots, and hard constraints allow it.
- If Kairouan can be served on a reasonable return alternative from Mahdia/Sousse back to Coficab, allow Kairouan insertion on that same itinerary.
- If Jendouba is in the opposite direction, route it separately unless there is a strong OSRM route-saving reason and constraints allow it.

Recommended implementation:
- Build an OSRM duration/distance matrix for all stops plus depot.
- Compute route insertion cost: extra distance/time caused by inserting a stop into an existing ordered route.
- Compute route savings for pairing/grouping stops compared with separate depot-stop-depot trips.
- Prefer assignments with low marginal insertion cost or high route savings, while preserving capacity and hard constraints.
- Run OR-Tools on the OSRM matrix after candidate grouping, or encode vehicles directly with the matrix and let the objective minimize total road duration/distance plus requested-slot penalties.

## Error Handling

If a coordinate is missing:
- mark delivery unassigned with `Missing client coordinates`.

If OSRM table has null duration/distance:
- mark affected delivery unrouteable or exclude that edge from feasible optimization.

If OSRM service is unavailable:
- return a clear backend error for generation.
- do not silently display haversine or hardcoded values as accurate route estimates.

If frontend manual edits change stop order or timing:
- call a backend recalculate endpoint with the updated sequence.
- recompute OSRM route legs and timings.
- preserve manual override labels if dispatcher intentionally overrides computed values.

## Verification Checklist

- No generated planning UI uses `getClientPosition` or fabricated coordinate fallback.
- No final displayed distance/ETA uses haversine.
- No route endpoint returns placeholder distances like `1000` or `850`.
- Depot coordinate comes from config or DB, not hardcoded `36.5,10.1`.
- `total_distance_km` equals the sum of OSRM route legs.
- `total_travel_min` equals the sum of OSRM route leg durations.
- ETA/departure sequence equals travel plus service plus waiting rules.
- Excel `ETD`/`ETA` are not inserted into `constraints.time_window`; they are retained as soft requested-slot values.
- Handling time uses 5 minutes per palette/position by default.
- Same-corridor/backhaul fixture such as Sousse/Mahdia/Kairouan/Jendouba produces an east/central route and a separate northwest route when capacities allow.
- Unrouteable deliveries are shown with actionable reasons.
