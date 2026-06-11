"use client";

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const TUNISIA_CENTER = [35.8, 9.6];
const PALETTE = ['#7c3aed', '#2563eb', '#059669', '#d97706', '#dc2626', '#0891b2', '#9333ea', '#65a30d'];

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const coord = (o) => (o && isNum(o.lat) && isNum(o.lon) ? [o.lat, o.lon] : (o && isNum(o.lat) && isNum(o.lng) ? [o.lat, o.lng] : null));

// Build, per truck, the ordered list of trips with their depot→stops→depot
// point sequences (straight legs — travel times are haversine-based, the road
// network is not modelled). Only stops with real coordinates are included.
function buildRoutes(plan) {
  const depot = coord(plan?.depot);
  return (plan?.trucks || []).map((truck, ti) => {
    const color = PALETTE[ti % PALETTE.length];
    const trips = (truck.trips || []).map((trip) => {
      const stops = (trip.stops || [])
        .map((s) => ({ ...s, _pt: coord(s) }))
        .filter((s) => s._pt);
      const path = [];
      if (depot) path.push(depot);
      stops.forEach((s) => path.push(s._pt));
      if (depot && stops.length) path.push(depot);
      return { trip_id: trip.trip_id, stops, path };
    }).filter((t) => t.stops.length);
    const stopCount = trips.reduce((n, t) => n + t.stops.length, 0);
    return { truck, color, trips, stopCount };
  });
}

// Imperatively fit the map to whatever is currently in focus (the selected
// truck's stops, or the whole plan when nothing is selected).
function FitBounds({ routes, selectedId, depot }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    const inFocus = selectedId != null
      ? routes.filter((r) => String(r.truck.truck_id) === String(selectedId))
      : routes;
    const pts = [];
    if (depot) pts.push(depot);
    inFocus.forEach((r) => r.trips.forEach((t) => t.stops.forEach((s) => pts.push(s._pt))));
    if (pts.length === 1) {
      map.setView(pts[0], 9);
    } else if (pts.length > 1) {
      map.fitBounds(pts, { padding: [40, 40] });
    }
  }, [routes, selectedId, depot, map]);
  return null;
}

function MapInner({ plan, selectedTruckId, onSelectTruck, height }) {
  const routes = useMemo(() => buildRoutes(plan), [plan]);
  const depot = coord(plan?.depot);
  const hasSelection = selectedTruckId != null;

  return (
    <MapContainer center={depot || TUNISIA_CENTER} zoom={7} className="h-full w-full" scrollWheelZoom>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds routes={routes} selectedId={selectedTruckId} depot={depot} />

      {/* Routes: faint by default, the selected truck's route is bold + numbered */}
      {routes.map((r) => {
        const selected = String(r.truck.truck_id) === String(selectedTruckId);
        const dim = hasSelection && !selected;
        return r.trips.map((t) => (
          <Polyline
            key={`${r.truck.truck_id}-${t.trip_id}`}
            positions={t.path}
            pathOptions={{
              color: r.color,
              weight: selected ? 5 : 3,
              opacity: dim ? 0.18 : selected ? 0.95 : 0.55,
              dashArray: selected ? null : '6 6',
            }}
            eventHandlers={{ click: () => onSelectTruck?.(r.truck.truck_id) }}
          />
        ));
      })}

      {/* Numbered stop markers for the selected truck only (keeps it readable) */}
      {routes.filter((r) => String(r.truck.truck_id) === String(selectedTruckId)).map((r) => {
        let order = 0;
        return r.trips.flatMap((t) => t.stops.map((s) => {
          order += 1;
          return (
            <CircleMarker
              key={`${r.truck.truck_id}-${s.id}`}
              center={s._pt}
              radius={11}
              pathOptions={{ color: '#fff', weight: 2, fillColor: r.color, fillOpacity: 1 }}
            >
              <Tooltip permanent direction="center" className="route-stop-num">{order}</Tooltip>
              <Popup>
                <div className="space-y-0.5 text-slate-900">
                  <p className="font-semibold">{s.client}</p>
                  <p className="text-xs">{s.resolved_location || s.end_location || ''}</p>
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

      {/* Depot */}
      {depot && (
        <CircleMarker center={depot} radius={9} pathOptions={{ color: '#1a1a2e', weight: 3, fillColor: '#facc15', fillOpacity: 1 }}>
          <Tooltip direction="top">COFICAB Mégrine (depot)</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}

export default function RouteMap({ plan, selectedTruckId = null, onSelectTruck, height = 460 }) {
  const [isClient, setIsClient] = useState(false);
  useEffect(() => setIsClient(true), []);

  const routes = useMemo(() => buildRoutes(plan), [plan]);
  const activeRoutes = routes.filter((r) => r.stopCount > 0);
  const selected = routes.find((r) => String(r.truck.truck_id) === String(selectedTruckId));

  return (
    <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#7c3aed]">Truck routes</p>
          <p className="mt-1 text-xs text-[#6b6b7b]">
            {selected
              ? `Showing ${selected.truck.truck_label} — ${selected.stopCount} stop${selected.stopCount > 1 ? 's' : ''} from the depot`
              : 'Select a truck below or in the timeline to trace its road.'}
          </p>
        </div>
        {selectedTruckId != null && (
          <button
            type="button"
            onClick={() => onSelectTruck?.(null)}
            className="rounded-full border border-[#e8e5df] px-3 py-1 text-xs font-semibold text-[#6b6b7b] transition hover:bg-[#faf8f5]"
          >
            Show all
          </button>
        )}
      </div>

      {/* Clickable truck legend */}
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
          <MapInner plan={plan} selectedTruckId={selectedTruckId} onSelectTruck={onSelectTruck} height={height} />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-[#f0eee9] text-sm text-[#9e9aa4]">Loading map…</div>
        )}
      </div>
    </div>
  );
}
