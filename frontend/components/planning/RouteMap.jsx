"use client";

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const TUNISIA_CENTER = [35.8, 9.6];
const PALETTE = ['#7c3aed', '#2563eb', '#059669', '#d97706', '#dc2626', '#0891b2', '#9333ea', '#65a30d'];
const UNASSIGNED_COLOR = '#9ca3af';

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const coord = (o) => {
  const lat = o?.lat ?? o?.latitude;
  const lon = o?.lon ?? o?.lng ?? o?.longitude;
  return isNum(Number(lat)) && isNum(Number(lon)) && (lat || lon) ? [Number(lat), Number(lon)] : null;
};

// Per truck: ordered trips, each a depot -> stops -> depot point sequence
// (straight legs — travel times are haversine-based, roads aren't modelled).
function buildRoutes(plan) {
  const depot = coord(plan?.depot);
  return (plan?.trucks || []).map((truck, ti) => {
    const color = PALETTE[ti % PALETTE.length];
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

function FitBounds({ routes, unassigned, selectedId, depot }) {
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
  }, [routes, unassigned, selectedId, depot, map]);
  return null;
}

// Snap a trip's waypoints (depot -> stops -> depot) to the real road network
// via the public OSRM server. Returns [[lat,lng], ...] following the roads, or
// null on any failure so the caller falls back to straight legs.
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

function MapInner({ plan, selectedTruckId, onSelectTruck }) {
  const routes = useMemo(() => buildRoutes(plan), [plan]);
  const depot = coord(plan?.depot);
  const unassigned = useMemo(
    () => (plan?.unassigned || []).map((u) => ({ ...u, _pt: coord(u) })).filter((u) => u._pt),
    [plan],
  );
  const hasSelection = selectedTruckId != null;

  // Real road geometry per trip, keyed by truck-trip id. Drawn instead of the
  // straight legs once OSRM responds; straight legs show meanwhile / on failure.
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
      if (!cancelled) {
        setRoads(Object.fromEntries(entries.filter(([, g]) => g)));
      }
    })();
    return () => { cancelled = true; };
  }, [routes]);

  return (
    <MapContainer center={depot || TUNISIA_CENTER} zoom={7} scrollWheelZoom className="h-full w-full">
      <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <FitBounds routes={routes} unassigned={unassigned} selectedId={selectedTruckId} depot={depot} />

      {/* Every truck's route. Selected one is bold + solid; the rest stay visible
          (dashed) so the whole day is shown, dimming only when one is focused. */}
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

      {/* Every client stop. Without a selection all are shown as colored dots;
          the focused truck's stops become numbered in delivery order. */}
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

      {/* Today's clients that couldn't be routed — shown in grey so "all clients"
          really means all of them. */}
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

      {depot && (
        <CircleMarker center={depot} radius={9} pathOptions={{ color: '#1a1a2e', weight: 3, fillColor: '#facc15', fillOpacity: 1 }}>
          <Tooltip direction="top">COFICAB Sidi Hassine (depot)</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}

export default function RouteMap({ plan, selectedTruckId = null, onSelectTruck, height = 520 }) {
  const [isClient, setIsClient] = useState(false);
  useEffect(() => setIsClient(true), []);

  const routes = useMemo(() => buildRoutes(plan), [plan]);
  const activeRoutes = routes.filter((r) => r.stopCount > 0);
  const selected = routes.find((r) => String(r.truck.truck_id) === String(selectedTruckId));
  const totalStops = activeRoutes.reduce((n, r) => n + r.stopCount, 0);
  const unassignedCount = (plan?.unassigned || []).length;

  return (
    <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#7c3aed]">Today’s routes</p>
          <p className="mt-1 text-xs text-[#6b6b7b]">
            {selected
              ? `${selected.truck.truck_label} — ${selected.stopCount} stop${selected.stopCount > 1 ? 's' : ''} from the depot`
              : `${activeRoutes.length} truck${activeRoutes.length > 1 ? 's' : ''} · ${totalStops} client${totalStops > 1 ? 's' : ''}${unassignedCount ? ` · ${unassignedCount} unassigned` : ''}`}
          </p>
        </div>
        {selectedTruckId != null && (
          <button
            type="button"
            onClick={() => onSelectTruck?.(null)}
            className="rounded-full border border-[#e8e5df] px-3 py-1 text-xs font-semibold text-[#6b6b7b] transition hover:bg-[#faf8f5]"
          >
            Show all trucks
          </button>
        )}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {activeRoutes.map((r) => {
          const on = String(r.truck.truck_id) === String(selectedTruckId);
          return (
            <button
              key={r.truck.truck_id}
              type="button"
              onClick={() => onSelectTruck?.(on ? null : r.truck.truck_id)}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition ${
                on ? 'border-[#7c3aed] bg-[#7c3aed]/10 text-[#7c3aed]' : 'border-[#e8e5df] text-[#1a1a2e] hover:bg-[#faf8f5]'
              }`}
            >
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: r.color }} />
              {r.truck.truck_label}
              <span className="text-[#9e9aa4]">· {r.stopCount}</span>
            </button>
          );
        })}
        {!activeRoutes.length && <span className="text-xs text-[#9e9aa4]">No routed deliveries to map.</span>}
      </div>

      <div className="overflow-hidden rounded-[1.25rem] border border-[#ece8e1]" style={{ height }}>
        {isClient ? (
          <MapInner plan={plan} selectedTruckId={selectedTruckId} onSelectTruck={onSelectTruck} />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-[#f0eee9] text-sm text-[#9e9aa4]">Loading map…</div>
        )}
      </div>
    </div>
  );
}
