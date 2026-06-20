"use client";

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { palette } from '@/lib/theme';

const TUNISIA_CENTER = [35.8, 9.6];

// Per-truck route colours (matches the chips in ControlTowerPanel, by truck index).
export const ROUTE_PALETTE = [
  palette.brand[600], '#2563eb', '#059669', palette.warning, palette.danger, '#0891b2', '#9333ea', '#65a30d',
];
const UNASSIGNED_COLOR = '#9ca3af';

// Live-state → colour for the moving truck markers. Mirrors the legend.
const STATE_COLOR = {
  en_route: '#2563eb',
  at_stop: '#059669',
  returning: '#7c3aed',
  reloading: '#d97706',
  idle: '#9ca3af',
  pre_dispatch: '#9ca3af',
  completed: '#64748b',
};

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const coord = (o) => {
  const lat = o?.lat ?? o?.latitude;
  const lon = o?.lon ?? o?.lng ?? o?.longitude;
  return isNum(Number(lat)) && isNum(Number(lon)) && (lat || lon) ? [Number(lat), Number(lon)] : null;
};

// Per truck: ordered trips, each a depot -> stops -> depot point sequence.
function buildRoutes(plan) {
  const depot = coord(plan?.depot);
  return (plan?.trucks || []).map((truck, ti) => {
    const color = ROUTE_PALETTE[ti % ROUTE_PALETTE.length];
    const trips = (truck.trips || []).map((trip) => {
      const stops = (trip.stops || []).map((s) => ({ ...s, _pt: coord(s) })).filter((s) => s._pt);
      const path = [];
      if (depot) path.push(depot);
      stops.forEach((s) => path.push(s._pt));
      if (depot && stops.length) path.push(depot);
      return { trip_id: trip.trip_id, stops, path };
    }).filter((t) => t.stops.length);
    return { truck, color, trips, stopCount: trips.reduce((n, t) => n + t.stops.length, 0) };
  });
}

// Snap a trip's waypoints to the road network via OSRM; null on failure so the
// caller falls back to straight legs.
async function fetchRoadGeometry(path) {
  if (path.length < 2) return null;
  const coords = path.map(([la, lo]) => `${lo},${la}`).join(';');
  const url = `https://router.project-osrm.org/route/v1/driving/${coords}?overview=simplified&geometries=geojson`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    const g = data?.routes?.[0]?.geometry?.coordinates;
    return Array.isArray(g) ? g.map(([lo, la]) => [la, lo]) : null;
  } catch {
    return null;
  }
}

// Fit the map when the plan/truck-set or selection changes — not on every clock
// tick, so the view doesn't jump while trucks animate along their routes.
function FitBounds({ routes, unassigned, selectedId, depot, fitKey }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    const inFocus = selectedId != null
      ? routes.filter((r) => String(r.truck.truck_id) === String(selectedId))
      : routes;
    const pts = [];
    if (depot) pts.push(depot);
    inFocus.forEach((r) => r.trips.forEach((t) => t.stops.forEach((s) => pts.push(s._pt))));
    if (selectedId == null) unassigned.forEach((u) => pts.push(u._pt));
    if (pts.length === 1) map.setView(pts[0], 9);
    else if (pts.length > 1) map.fitBounds(pts, { padding: [40, 40], maxZoom: 11 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, selectedId]);
  return null;
}

function MapInner({ plan, snapshot, selectedTruckId, onSelectTruck }) {
  const routes = useMemo(() => buildRoutes(plan), [plan]);
  const depot = coord(snapshot?.depot) || coord(plan?.depot);
  const unassigned = useMemo(
    () => (plan?.unassigned || []).map((u) => ({ ...u, _pt: coord(u) })).filter((u) => u._pt),
    [plan],
  );
  const hasSelection = selectedTruckId != null;
  const liveTrucks = (snapshot?.trucks || []).filter((t) => Array.isArray(t.position));
  const alerts = (snapshot?.alerts || []).filter((a) => coord(a));
  const fitKey = `${plan?.plan_id || ''}:${(plan?.trucks || []).length}`;

  // Real road geometry per trip (drawn instead of straight legs once OSRM responds).
  const [roads, setRoads] = useState({});
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(
        routes.flatMap((r) => r.trips.map(async (t) => {
          const geom = await fetchRoadGeometry(t.path);
          return [`${r.truck.truck_id}-${t.trip_id}`, geom];
        })),
      );
      if (!cancelled) setRoads(Object.fromEntries(entries.filter(([, g]) => g)));
    })();
    return () => { cancelled = true; };
  }, [routes]);

  return (
    <MapContainer center={depot || TUNISIA_CENTER} zoom={7} scrollWheelZoom className="h-full w-full">
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <FitBounds routes={routes} unassigned={unassigned} selectedId={selectedTruckId} depot={depot} fitKey={fitKey} />

      {/* Planned routes per truck (real roads). Selected one is bold + solid;
          the rest stay visible (dashed) so the whole day is shown. */}
      {routes.map((r) => {
        const selected = String(r.truck.truck_id) === String(selectedTruckId);
        const dim = hasSelection && !selected;
        return r.trips.map((t) => (
          <Polyline
            key={`${r.truck.truck_id}-${t.trip_id}`}
            positions={roads[`${r.truck.truck_id}-${t.trip_id}`] || t.path}
            pathOptions={{
              color: r.color,
              weight: selected ? 5 : 3,
              opacity: dim ? 0.15 : selected ? 0.95 : 0.6,
              dashArray: selected ? null : '6 6',
            }}
            eventHandlers={{ click: () => onSelectTruck?.(r.truck.truck_id) }}
          />
        ));
      })}

      {/* Client stops. Without a selection all show as colored dots; the focused
          truck's stops become numbered in delivery order. */}
      {routes.map((r) => {
        const selected = String(r.truck.truck_id) === String(selectedTruckId);
        const dim = hasSelection && !selected;
        let order = 0;
        return r.trips.flatMap((t) => t.stops.map((s) => {
          order += 1;
          return (
            <CircleMarker
              key={`${r.truck.truck_id}-${s.id}`}
              center={s._pt}
              radius={selected ? 11 : 6}
              pathOptions={{ color: '#fff', weight: selected ? 2 : 1, fillColor: r.color, fillOpacity: dim ? 0.25 : 1 }}
              eventHandlers={{ click: () => onSelectTruck?.(r.truck.truck_id) }}
            >
              {selected && <Tooltip permanent direction="center" className="route-stop-num">{order}</Tooltip>}
              <Popup>
                <div className="space-y-0.5 text-slate-900">
                  <p className="font-semibold">{s.client}</p>
                  <p className="text-xs">{r.truck.truck_label} · {s.resolved_location || s.end_location || ''}</p>
                  <p className="text-xs">{s.etd} → {s.eta}</p>
                  <p className="text-xs">
                    {Number(s.quantity_positions || s.position_count || 0)} pos
                    {s.quantity_kg ? ` · ${Number(s.quantity_kg).toLocaleString()} kg` : ''}
                  </p>
                </div>
              </Popup>
            </CircleMarker>
          );
        }));
      })}

      {/* Unassigned clients (grey) so "all clients" really means all of them. */}
      {unassigned.map((u, i) => (
        <CircleMarker
          key={`un-${u.id || i}`}
          center={u._pt}
          radius={6}
          pathOptions={{ color: '#fff', weight: 1, fillColor: UNASSIGNED_COLOR, fillOpacity: hasSelection ? 0.3 : 0.9 }}
        >
          <Popup>
            <div className="space-y-0.5 text-slate-900">
              <p className="font-semibold">{u.client}</p>
              <p className="text-xs text-red-600">Unassigned{u.unassigned_reason ? ` — ${u.unassigned_reason}` : ''}</p>
            </div>
          </Popup>
        </CircleMarker>
      ))}

      {/* Predicted-late / geofence alert markers (red) — live overlay. */}
      {alerts.map((a, i) => (
        <CircleMarker
          key={`alert-${a.truck_id}-${i}`}
          center={coord(a)}
          radius={a.severity === 'high' ? 13 : 10}
          pathOptions={{ color: '#fff', weight: 2, fillColor: a.severity === 'high' ? '#dc2626' : '#f59e0b', fillOpacity: 0.9 }}
        >
          <Popup>
            <div className="space-y-0.5 text-slate-900">
              <p className="font-semibold">{a.client}</p>
              <p className="text-xs text-red-600">Predicted {a.minutes_late} min late ({a.truck_label})</p>
              <p className="text-xs">window ≤ {a.window_end} · ETA {a.projected_arrival}</p>
            </div>
          </Popup>
        </CircleMarker>
      ))}

      {/* Live truck positions at the scrubbed time, coloured by state — overlay. */}
      {liveTrucks.map((t) => {
        const dim = hasSelection && String(t.truck_id) !== String(selectedTruckId);
        const color = STATE_COLOR[t.state] || '#2563eb';
        return (
          <CircleMarker
            key={`live-${t.truck_id}`}
            center={t.position}
            radius={10}
            pathOptions={{ color: '#fff', weight: 3, fillColor: color, fillOpacity: dim ? 0.3 : 1 }}
            eventHandlers={{ click: () => onSelectTruck?.(t.truck_id) }}
          >
            <Tooltip permanent direction="top" offset={[0, -6]} className="ct-truck-label">
              {t.truck_label}
            </Tooltip>
            <Popup>
              <div className="space-y-0.5 text-slate-900">
                <p className="font-semibold">{t.truck_label}</p>
                <p className="text-xs capitalize">{String(t.state).replace('_', ' ')}{t.delay_min ? ` · +${t.delay_min} min behind` : ''}</p>
                {t.next_stop ? <p className="text-xs">Next: {t.next_stop.client} (ETA {t.next_stop.eta})</p> : null}
                <p className="text-xs">{t.completed_stops}/{t.total_stops} stops · {t.day_progress_pct}% of day</p>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}

      {depot && (
        <CircleMarker center={depot} radius={9} pathOptions={{ color: palette.ink, weight: 3, fillColor: '#facc15', fillOpacity: 1 }}>
          <Tooltip direction="top">COFICAB Sidi Hassine (depot)</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}

export default function ControlTowerMap({ plan, snapshot, selectedTruckId = null, onSelectTruck, height = 480 }) {
  const [isClient, setIsClient] = useState(false);
  useEffect(() => setIsClient(true), []);

  return (
    <div className="overflow-hidden rounded-[1.25rem] border border-[#ece8e1]" style={{ height }}>
      {isClient ? (
        <MapInner plan={plan} snapshot={snapshot} selectedTruckId={selectedTruckId} onSelectTruck={onSelectTruck} />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-[#f0eee9] text-sm text-[#9e9aa4]">Loading map…</div>
      )}
    </div>
  );
}
