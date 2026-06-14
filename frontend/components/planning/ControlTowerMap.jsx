"use client";

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const TUNISIA_CENTER = [35.8, 9.6];

// Live-state → colour. Mirrors the legend in ControlTowerPanel.
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

// Dimmed planned route per truck (depot → stops → depot) for spatial context.
function buildRoutes(plan) {
  const depot = coord(plan?.depot);
  return (plan?.trucks || []).map((truck) => {
    const path = [];
    (truck.trips || []).forEach((trip) => {
      if (depot) path.push(depot);
      (trip.stops || []).forEach((s) => { const p = coord(s); if (p) path.push(p); });
      if (depot && (trip.stops || []).length) path.push(depot);
    });
    return { truck_id: truck.truck_id, path };
  }).filter((r) => r.path.length > 1);
}

// Fit the map once per plan/truck-set change — not on every clock tick, so the
// view doesn't jump while the trucks animate along their routes.
function FitOnce({ plan, depot, fitKey }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    const pts = [];
    if (depot) pts.push(depot);
    (plan?.trucks || []).forEach((t) => (t.trips || []).forEach((trip) =>
      (trip.stops || []).forEach((s) => { const p = coord(s); if (p) pts.push(p); })));
    if (pts.length === 1) map.setView(pts[0], 9);
    else if (pts.length > 1) map.fitBounds(pts, { padding: [40, 40], maxZoom: 11 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);
  return null;
}

function MapInner({ plan, snapshot }) {
  const routes = useMemo(() => buildRoutes(plan), [plan]);
  const depot = coord(snapshot?.depot) || coord(plan?.depot);
  const trucks = (snapshot?.trucks || []).filter((t) => Array.isArray(t.position));
  const alerts = (snapshot?.alerts || []).filter((a) => coord(a));
  const fitKey = `${plan?.plan_id || ''}:${(plan?.trucks || []).length}`;

  return (
    <MapContainer center={depot || TUNISIA_CENTER} zoom={7} scrollWheelZoom className="h-full w-full">
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <FitOnce plan={plan} depot={depot} fitKey={fitKey} />

      {/* Dimmed planned routes for context */}
      {routes.map((r) => (
        <Polyline
          key={`route-${r.truck_id}`}
          positions={r.path}
          pathOptions={{ color: '#94a3b8', weight: 2, opacity: 0.35, dashArray: '5 7' }}
        />
      ))}

      {/* Predicted-late / geofence alert markers (red) */}
      {alerts.map((a, i) => (
        <CircleMarker
          key={`alert-${a.truck_id}-${i}`}
          center={coord(a)}
          radius={a.severity === 'high' ? 12 : 9}
          pathOptions={{ color: '#fff', weight: 2, fillColor: a.severity === 'high' ? '#dc2626' : '#f59e0b', fillOpacity: 0.9 }}
        >
          <Popup>
            <div className="space-y-0.5 text-slate-900">
              <p className="font-semibold">{a.client}</p>
              <p className="text-xs text-red-600">
                Predicted {a.minutes_late} min late ({a.truck_label})
              </p>
              <p className="text-xs">window ≤ {a.window_end} · ETA {a.projected_arrival}</p>
            </div>
          </Popup>
        </CircleMarker>
      ))}

      {/* Live truck positions, coloured by state */}
      {trucks.map((t) => {
        const color = STATE_COLOR[t.state] || '#2563eb';
        return (
          <CircleMarker
            key={`truck-${t.truck_id}`}
            center={t.position}
            radius={9}
            pathOptions={{ color: '#fff', weight: 2, fillColor: color, fillOpacity: 1 }}
          >
            <Tooltip permanent direction="top" offset={[0, -6]} className="ct-truck-label">
              {t.truck_label}
            </Tooltip>
            <Popup>
              <div className="space-y-0.5 text-slate-900">
                <p className="font-semibold">{t.truck_label}</p>
                <p className="text-xs capitalize">{String(t.state).replace('_', ' ')}{t.delay_min ? ` · +${t.delay_min} min behind` : ''}</p>
                {t.next_stop ? (
                  <p className="text-xs">Next: {t.next_stop.client} (ETA {t.next_stop.eta})</p>
                ) : null}
                <p className="text-xs">{t.completed_stops}/{t.total_stops} stops · {t.day_progress_pct}% of day</p>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}

      {depot && (
        <CircleMarker center={depot} radius={8} pathOptions={{ color: '#1f2937', weight: 3, fillColor: '#facc15', fillOpacity: 1 }}>
          <Tooltip direction="top">COFICAB Sidi Hassine (depot)</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}

export default function ControlTowerMap({ plan, snapshot, height = 460 }) {
  const [isClient, setIsClient] = useState(false);
  useEffect(() => setIsClient(true), []);

  return (
    <div className="overflow-hidden rounded-[1.25rem] border border-[#ece8e1]" style={{ height }}>
      {isClient ? (
        <MapInner plan={plan} snapshot={snapshot} />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-[#f0eee9] text-sm text-[#9e9aa4]">Loading map…</div>
      )}
    </div>
  );
}
