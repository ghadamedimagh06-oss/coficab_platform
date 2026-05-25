# Reference — API Contracts

Catalog of every backend endpoint. Each row notes which KPI it feeds (consumes / produces).

## Conventions
- All endpoints prefixed `/api`.
- Auth: `Authorization: Bearer <jwt>` unless marked **public**.
- Errors: `{ "detail": "<reason>" }` with appropriate HTTP code.

---

## Auth (`/api/auth`)

| Method | Path | Roles | Body | Returns |
|---|---|---|---|---|
| POST | `/login` | public | `{ username, password }` | `{ access_token, role }` |
| GET  | `/me` | any | — | `{ id, username, email, role }` |
| POST | `/users` | admin | `{ username, email, password, role }` | created user |
| PATCH| `/users/{id}` | admin | `{ role?, is_active? }` | updated user |

---

## Fleet (`/api/fleet`)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/trucks` | any | list, with `status`, `capacite_kg`, `chauffeur_defaut` |
| POST| `/trucks` | admin | create |
| PATCH| `/trucks/{id}` | planner+admin | status change |
| GET | `/drivers` | any | list with current shift status |
| POST| `/drivers` | admin | create |
| PATCH| `/drivers/{id}` | admin | edit |
| GET | `/utilization` | any | `{ "trucks": [{ "plate":"TR-01","utilization_pct": 87 }] }` for dashboard |

---

## Clients (`/api/clients`)

| Method | Path | Roles |
|---|---|---|
| GET | `/` | any |
| POST | `/` | planner+admin |
| PATCH | `/{id}` | planner+admin |
| GET | `/{id}` | any (includes demandes history) |

---

## Ingestion (`/api/ingestion`)

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/upload` | admin | multipart, single Excel file |
| POST | `/demande` | planner+admin | one demande JSON |
| GET | `/logs` | any | last N |
| POST | `/logs/{id}/retry` | admin | re-run a failed file |

---

## Optimization (`/api/optimization`)

| Method | Path | Roles | Body |
|---|---|---|---|
| POST | `/run` | planner+admin | `{ day:"YYYY-MM-DD", weights?:{alpha,beta,gamma,delta,epsilon} }` |
| GET  | `/plan/{id}` | any | full plan |
| GET  | `/plan/{id}/kpis` | any | KPI preview for this plan |
| GET  | `/weights` | any | current optimizer weights |
| POST | `/weights` | admin | update defaults |

---

## Planning (`/api/planning`)

> Feeds: R4-02 OTD (validated plan defines ETAs), R4 Load Efficiency, Premium Freight (mode flag), audit trail.

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET  | `/?date=YYYY-MM-DD` | any | most recent plan for the day |
| GET  | `/{plan_version_id}` | any | full plan with missions + stops |
| GET  | `/{plan_version_id}/impact` | any | KPI preview, polled on each drag |
| POST | `/{plan_version_id}/reassign` | planner+admin | `{ demande_id, target_mission_id, reason }` |
| POST | `/{plan_version_id}/validate` | planner+admin | locks; fires dispatch |
| POST | `/{plan_version_id}/clone` | planner+admin | new DRAFT version from any version |
| GET  | `/{plan_version_id}/changelog` | any | audit rows |

---

## Dispatch (`/api/dispatch`)

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET  | `/missions/{id}/brief` | any | text brief preview |
| POST | `/missions/{id}/resend` | planner+admin | manual resend |
| GET  | `/logs?date=` | any | notification attempts |

---

## Tracking (`/api/tracking`)

> Produces: R4-02 OTD, R4-06 OTIF (close-out endpoint).

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET  | `/live` | any | active missions, ETAs, load % |
| GET  | `/missions/{id}/status` | any | per-stop slip |
| POST | `/stops/{id}/delivered` | planner+admin | `{ quantite_livree_kg }` — feeds OTD/OTIF |

---

## Incidents (`/api/incidents`)

> Produces: R4-12 Customer Logistics Incidents/MKm.

| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/` | planner+admin | `{ type, description, mission_id?, demande_id?, impact_delai_min?, cause? }` |
| POST | `/{id}/resolve` | planner+admin | `{ note }` |
| GET  | `/?from=&to=&type=&resolu=` | any | paginated |
| GET  | `/{id}` | any | detail |
| GET  | `/stats?month=YYYY-MM` | any | counts + delay totals |

---

## Metrics (`/api/metrics`)

> The dashboard data plane. Reads `kpi_journalier` / `kpi_mensuel`.

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET | `/kpi` | any | dashboard payload (all KPIs, today + current month aggregates) |
| GET | `/kpi/{code}` | any | history for one KPI (`?from=&to=&period=daily\|monthly`) |
| GET | `/kpi/snapshot/daily?date=` | any | every KPI for one day |
| GET | `/kpi/snapshot/monthly?ym=YYYY-MM` | any | every KPI for one month |
| POST| `/kpi/recompute` | admin | `{ from, to }` |
| GET | `/deliveries/weekly` | any | for `weeklyData` chart on dashboard |
| GET | `/efficiency/distribution` | any | for the donut |
| GET | `/timeline` | any | for the timeline events on dashboard |

---

## Dashboard payload shape

`GET /api/metrics/kpi`:

```json
{
  "as_of": "2026-05-25T22:30:00Z",
  "kpis": [
    {
      "code": "R4-06", "label": "OTIF", "unit": "%",
      "value": 92.54, "target": 96, "color": "yellow", "trend": -1.2,
      "horizon": "monthly"
    },
    {
      "code": "R4-02", "label": "OTD", "unit": "%",
      "value": 93.57, "target": 96, "color": "yellow", "trend": 0.8,
      "horizon": "monthly"
    },
    {
      "code": "R4-13", "label": "Fuel Consumption Efficiency", "unit": "mL/T.km",
      "value": 0.15, "target": 0.14, "color": "green", "trend": -0.01,
      "horizon": "daily"
    },
    {
      "code": "R5-10", "label": "Logistics Cost", "unit": "€/T",
      "value": 17.1, "target": 16, "color": "green", "trend": -0.4,
      "horizon": "monthly"
    },
    {
      "code": "R4-02-PF", "label": "Premium Freight Cost", "unit": "EUR",
      "value": 4125, "target": 1500, "color": "red", "trend": 0.0,
      "horizon": "monthly"
    },
    {
      "code": "R4-03", "label": "Premium Freight Occurrences", "unit": "Nb",
      "value": 2, "target": 1, "color": "green", "trend": 0.0,
      "horizon": "monthly"
    },
    {
      "code": "R4-12", "label": "Customer Logistics Incidents", "unit": "Nb/MKm",
      "value": 0, "target": 13, "color": "grey", "trend": 0.0,
      "horizon": "monthly"
    },
    {
      "code": "R4", "label": "Load Efficiency Rate", "unit": "%",
      "value": 74, "target": 80, "color": "yellow", "trend": 1.5,
      "horizon": "daily"
    }
  ]
}
```

This matches the monthly report screenshot. The frontend's existing dashboard tile layout consumes it via the `toCardShape` adapter (skill 09).

---

## Versioning

API version: `v1`. URL stays `/api/...` — no `/v1/` prefix needed for an internal tool. If a breaking change is introduced, add `/api/v2/...` next to `/api/...` and migrate the frontend on a flag.
