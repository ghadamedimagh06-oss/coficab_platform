"use client";

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Tooltip, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { palette } from '@/lib/theme';

const statusColor = {
  on_time: '#22c55e',
  slight_delay: '#f59e0b',
  critical_delay: '#ef4444',
};

const clientColor = '#3b82f6';
const depotColor = '#facc15';
const TUNISIA_CENTER = [35.8, 9.6];
const DEPOT = { lat: 36.7708, lng: 10.1103, name: 'COFICAB Sidi Hassine (depot)' };

// Only real coordinates — never synthesise a position. Reads top-level lat/lng,
// latitude/longitude, or a nested location:{lat,lng} (the tracking payload
// shape). Returns null when no usable coordinate exists, so we simply don't
// plot that entity instead of dropping a fake marker on the map.
function position(entity) {
  const lat = entity?.lat ?? entity?.latitude ?? entity?.location?.lat;
  const lng = entity?.lng ?? entity?.longitude ?? entity?.location?.lng ?? entity?.location?.lon;
  const nlat = Number(lat);
  const nlng = Number(lng);
  if (!Number.isFinite(nlat) || !Number.isFinite(nlng)) return null;
  return [nlat, nlng];
}

// Keep the map on the Tunisian operating area; foreign export sites (e.g. Lyon)
// would otherwise zoom the whole view out to Europe.
const inTunisia = ([lat, lng]) => lat >= 30 && lat <= 38 && lng >= 7 && lng <= 12;

const statusOf = (truck) => {
  const s = truck.status?.toLowerCase() || '';
  if (s.includes('critical')) return 'critical_delay';
  if (s.includes('delay')) return 'slight_delay';
  return 'on_time';
};

function MapController({ points }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    if (points.length === 1) map.setView(points[0], 9);
    else if (points.length > 1) map.fitBounds(points, { padding: [40, 40], maxZoom: 11 });
  }, [map, points]);
  return null;
}

export default function TruckMap({ trucks = [], clients = [], height = 460, hideHeader = false }) {
  const [isClient, setIsClient] = useState(false);
  useEffect(() => setIsClient(true), []);

  // Clients with real, in-country coordinates.
  const clientPins = useMemo(() => (
    clients
      .map((c) => ({ ...c, _pt: position(c) }))
      .filter((c) => c._pt && inTunisia(c._pt))
  ), [clients]);

  // Trucks: de-duplicate by id and keep only those with a real position.
  const truckPins = useMemo(() => {
    const seen = new Map();
    trucks.forEach((t) => {
      const pt = position(t);
      if (pt) seen.set(String(t.transport_id || t.id), { ...t, _pt: pt });
    });
    return [...seen.values()].filter((t) => inTunisia(t._pt));
  }, [trucks]);

  const points = useMemo(
    () => [[DEPOT.lat, DEPOT.lng], ...clientPins.map((c) => c._pt), ...truckPins.map((t) => t._pt)],
    [clientPins, truckPins],
  );

  if (!isClient) {
    return (
      <div className="overflow-hidden rounded-[1.5rem] border border-[#ece8e1] bg-[#f0eee9]" style={{ height }}>
        <div className="flex h-full w-full items-center justify-center text-sm text-[#9e9aa4]">Loading map…</div>
      </div>
    );
  }

  return (
    <div className="rounded-[1.75rem] border border-border bg-white p-4 shadow-sm">
      {!hideHeader && (
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-600">Network</p>
            <h3 className="text-lg font-semibold text-ink">Delivery map</h3>
          </div>
          <div className="flex items-center gap-3 text-[11px] font-medium text-muted">
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: depotColor }} /> Depot</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: clientColor }} /> Client</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: statusColor.on_time }} /> Truck</span>
          </div>
        </div>
      )}
      <div className="overflow-hidden rounded-[1.5rem] border border-[#ece8e1]" style={{ height }}>
        <MapContainer center={TUNISIA_CENTER} zoom={7} scrollWheelZoom className="h-full w-full">
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapController points={points} />

          {clientPins.map((client, index) => (
            <CircleMarker
              key={client.id || `client-${index}`}
              center={client._pt}
              radius={7}
              pathOptions={{ color: '#fff', weight: 1.5, fillColor: clientColor, fillOpacity: 0.9 }}
            >
              <Popup>
                <div className="space-y-0.5 text-slate-900">
                  <p className="font-semibold">{client.customer || client.destination}</p>
                  <p className="text-xs">Destination: {client.destination || '—'}</p>
                  {client.km != null && <p className="text-xs">Distance: {client.km} km</p>}
                </div>
              </Popup>
            </CircleMarker>
          ))}

          {truckPins.map((truck, index) => {
            const status = statusOf(truck);
            return (
              <CircleMarker
                key={truck.transport_id || truck.id || `truck-${index}`}
                center={truck._pt}
                radius={9}
                pathOptions={{ color: '#fff', weight: 2, fillColor: statusColor[status], fillOpacity: 1 }}
              >
                <Popup>
                  <div className="space-y-0.5 text-slate-900">
                    <p className="font-semibold">{truck.transport_id || truck.id || `Truck ${index + 1}`}</p>
                    <p className="text-xs">{truck.status || 'On time'}</p>
                    {truck.eta_hours != null && <p className="text-xs">ETA: {Number(truck.eta_hours).toFixed(1)}h</p>}
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}

          <CircleMarker
            center={[DEPOT.lat, DEPOT.lng]}
            radius={9}
            pathOptions={{ color: palette.ink, weight: 3, fillColor: depotColor, fillOpacity: 1 }}
          >
            <Tooltip direction="top">{DEPOT.name}</Tooltip>
          </CircleMarker>
        </MapContainer>
      </div>
    </div>
  );
}
