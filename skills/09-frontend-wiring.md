# 09 — Frontend Wiring (UI unchanged)

> Goal: replace every mock-data import in `frontend/` with real API calls **without changing one Tailwind class, one icon, one color, or one card layout**. The visual identity is locked. Only the data source changes.

## KPI anchor
Every visible KPI cell on the dashboard, the planning page, and the analytics page must read from `kpi_journalier` / `kpi_mensuel` via the metrics API. The mock files in `frontend/data/` become unused (delete only after every page is migrated).

---

## Lock list — DO NOT modify

| Surface | Stays exactly as-is |
|---|---|
| Color palette | `#7c3aed`, `#6d28d9`, `#5b21b6` (sidebar gradient); `#f8f7f3` (background); `#1a1a2e` (titles); `#6b6b7b` (muted); `#e8e5df` (borders) |
| Icons | Every Lucide icon imported in every page |
| Charts | Recharts components (`AreaChart`, `BarChart`, `PieChart`, `ComposedChart`) |
| Cards | `bg-white rounded-2xl shadow-sm border border-[#e8e5df]` |
| Animations | Framer Motion variants (`container`, `item`) |
| Sidebar layout | `Sidebar.jsx` left rail, fixed 18rem width, purple gradient |
| Tailwind config | `frontend/tailwind.config.js` |

If a change to the API forces a UI tweak, **change the API to match the UI**, not the other way around.

---

## Folder additions

```
frontend/
├── lib/
│   ├── api.ts                  ← fetch wrapper + JWT injection
│   └── env.ts                  ← NEXT_PUBLIC_API_URL helper
├── hooks/
│   ├── useKpi.ts               ← SWR for /api/metrics/kpi
│   ├── usePlan.ts              ← SWR for /api/planning/:id
│   ├── usePlanImpact.ts        ← SWR for /api/planning/:id/impact
│   ├── useFleet.ts             ← SWR for trucks & drivers
│   ├── useClients.ts
│   ├── useDemandes.ts
│   ├── useIncidents.ts
│   └── useDispatch.ts
└── data/                       (mock files kept until each page is migrated)
```

---

## File: `frontend/lib/api.ts`

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: any) {
    super(message);
  }
}

function token() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("coficab_token");
}

export async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: token() ? { Authorization: `Bearer ${token()}` } : {},
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail || res.statusText, body);
  }
  return res.json();
}

export async function post<T>(path: string, payload: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail || res.statusText, body);
  }
  return res.json();
}
```

---

## File: `frontend/hooks/useKpi.ts`

```typescript
import useSWR from "swr";
import { fetcher } from "@/lib/api";

export type Kpi = {
  code: string;
  label: string;
  value: number;
  unit: string;
  color: "green" | "yellow" | "red" | "grey";
  target: number;
  trend: number;
};

export function useKpi() {
  const { data, error, isLoading, mutate } = useSWR<{ kpis: Kpi[] }>(
    "/api/metrics/kpi",
    fetcher,
    { refreshInterval: 60_000 } // re-poll every minute
  );
  return { kpis: data?.kpis ?? [], error, isLoading, mutate };
}
```

---

## Mapping the dashboard mock to the API response

Today, `frontend/app/dashboard/page.jsx` imports `kpiData` from `data/dashboardData.ts`. It looks like:

```typescript
const kpiData = [
  { id: 'deliveries', label: '...', value: '1,247', icon: 'truck', iconBg: '...',
    iconColor: '...', trend: 12.5, trendLabel: '...', sparklineData: [...] },
  ...
];
```

The migration is a small adapter that **converts the API shape into the existing mock shape** so JSX needs zero changes:

```jsx
// frontend/app/dashboard/page.jsx
import { useKpi } from '@/hooks/useKpi';

const ICON_MAP = {
  "R4-06": { id: 'otif',     icon: 'truck',         iconBg: 'rgba(124,58,237,0.1)', iconColor: '#7c3aed' },
  "R4-02": { id: 'otd',      icon: 'route',         iconBg: 'rgba(59,130,246,0.1)', iconColor: '#3b82f6' },
  "R4-13": { id: 'fuel',     icon: 'alert-triangle',iconBg: 'rgba(249,115,22,0.1)', iconColor: '#f97316' },
  "R5-10": { id: 'cost',     icon: 'bar-chart-3',   iconBg: 'rgba(20,184,166,0.1)', iconColor: '#14b8a6' },
  "R4":    { id: 'load',     icon: 'bar-chart-3',   iconBg: 'rgba(124,58,237,0.1)', iconColor: '#7c3aed' },
};

function toCardShape(kpi) {
  const meta = ICON_MAP[kpi.code] ?? {};
  return {
    id: meta.id ?? kpi.code,
    label: kpi.label,
    value: kpi.unit === '%' ? `${kpi.value.toFixed(1)}%` :
           kpi.unit === '€/T' ? `${kpi.value.toFixed(1)} €/T` :
           kpi.unit === 'EUR' ? `${kpi.value.toFixed(0)} €` :
           kpi.unit === 'mL/T.km' ? `${kpi.value.toFixed(2)}` :
           `${kpi.value}`,
    icon: meta.icon,
    iconBg: meta.iconBg,
    iconColor: meta.iconColor,
    trend: kpi.trend,
    trendLabel: 'vs last month',
    color: kpi.color,                 // NEW: for the colored border
    sparklineData: [],                // populated by /api/metrics/kpi/{code}/history
  };
}

export default function DashboardPage() {
  const { kpis } = useKpi();
  const cards = kpis.map(toCardShape);
  // ↓ unchanged JSX below — just uses `cards` instead of the imported mock
  // ...
}
```

Same pattern for `weeklyData` → `GET /api/metrics/deliveries/weekly`, `fleetData` → `GET /api/fleet/utilization`, `efficiencySegments` → `GET /api/metrics/efficiency/distribution`.

---

## Coloring KPI cards (no new components)

`StatCard.jsx` already renders a card body. Add an optional `accent` prop driven by `kpi.color`:

```jsx
// frontend/components/cards/StatCard.jsx — minimal addition
const accentMap = {
  green:  'border-l-4 border-l-emerald-500',
  yellow: 'border-l-4 border-l-amber-500',
  red:    'border-l-4 border-l-red-500',
};

export default function StatCard({ ..., accent }) {
  return (
    <div className={`bg-white rounded-2xl shadow-sm border border-[#e8e5df] p-5 ${accentMap[accent] ?? ''}`}>
      {/* rest unchanged */}
    </div>
  );
}
```

That's the only visual addition allowed — a left accent stripe matching the KPI band — and it can stay subtle (Tailwind colors that complement the existing palette).

---

## Page-by-page migration map

| Page | Today's mock | New hook | API endpoint |
|---|---|---|---|
| `/dashboard` | `kpiData`, `weeklyData`, `fleetData`, `efficiencySegments`, `timelineEvents`, `alerts` | `useKpi`, `useWeeklyDeliveries`, `useFleetUtilization` | `/api/metrics/kpi`, `/api/metrics/deliveries/weekly`, `/api/fleet/utilization`, `/api/metrics/timeline`, `/api/incidents?resolu=false` |
| `/planning` | `planningData` | `usePlan` | `/api/planning/{id}` |
| `/daily-planning` | `planningData` | `usePlan` (date-filtered) | `/api/planning?date=...` |
| `/transport/[id]` | `coficabData` | `useMission` | `/api/planning/missions/{id}` |
| `/vehicles` | `coficabData` | `useFleet` | `/api/fleet/trucks` |
| `/drivers` | `coficabData` | `useDrivers` | `/api/fleet/drivers` |
| `/clients` | `coficabData` | `useClients` | `/api/clients` |
| `/analytics` | `dashboardData` | `useKpiHistory` | `/api/metrics/kpi/{code}?from=&to=` |
| `/ai-monitor` | (mock) | `useIncidents`, `useDispatchLogs` | `/api/incidents`, `/api/dispatch/logs` |
| `/admin` | (mock) | `useIngestionLogs`, `useOptimizerWeights` | `/api/ingestion/logs`, `/api/optimization/weights` |
| `/map` | `coficabData` | `useMissionsLive` | `/api/tracking/live` |

Migrate one page at a time. Each migration:
1. Add the hook in `hooks/`.
2. Add the API endpoint if not present (skill `reference/api-contracts.md`).
3. In the page, swap `import { ... } from '@/data/...'` for the hook.
4. Add a tiny adapter (`toCardShape`-style) if the shape differs.
5. Add a loading skeleton **using the same card layout** (just `<div className="bg-white rounded-2xl ... animate-pulse"/>`).
6. Eyeball the page — same colors, same spacing.

---

## Environment

`frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The fetch wrapper reads this. In Docker compose, set it to the backend service hostname.

---

## Loading / empty / error states

Three rules, all using existing tokens:
- **Loading** — replace card body with `<div className="h-20 bg-[#f0eee9] animate-pulse rounded-xl" />`.
- **Empty** — render the card with `value="—"`, `color="grey"`.
- **Error** — show a tiny inline `<AlertTriangle className="text-red-500" size={14} />` next to the label. Tooltip = `error.message`.

No toasts, no modals, no full-screen takeover — the dashboard must always render the layout.

---

## Anti-patterns

- ❌ Adding new card components ("a fancier KPI card with bigger numbers"). Use the existing `StatCard`.
- ❌ Importing a new chart library. Recharts already covers everything needed.
- ❌ Restructuring `app/dashboard/page.jsx` into multiple files "for cleanliness". One page, one file, like today.
- ❌ Adding a global state library (Zustand/Redux). SWR is enough.
- ❌ Calling `/api/...` from inside `useEffect` instead of SWR. We need re-validation on focus and polling.

---

## Verification

1. Run backend (`uvicorn app.main:app`) and frontend (`npm run dev`).
2. Visit `/dashboard`. KPI cards show real values (or "—" with grey accent if no data yet).
3. Compare with a screenshot of the current mock dashboard. Layout, spacing, colors must be **pixel-identical** except KPI text values.
4. Throttle network in DevTools → cards show the pulse skeleton, never blank.
5. Stop the backend → cards show "—" + red AlertTriangle icon, layout still intact.
