"use client";

import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const statusColor = {
  on_time: '#22c55e',
  slight_delay: '#f59e0b',
  critical_delay: '#ef4444',
};

function normalizePosition(track, index) {
  if (track.lat && track.lng) {
    return [track.lat, track.lng];
  }
  const base = 48.8566 + index * 0.02;
  return [base, 2.3522 + index * 0.03];
}

export default function TruckMap({ trucks = [] }) {
  const center = trucks.length ? normalizePosition(trucks[0], 0) : [48.8566, 2.3522];
  return (
    <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-4 shadow-xl shadow-black/20">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-400">Real-time Positions</p>
          <h3 className="text-xl font-semibold">Live truck map</h3>
        </div>
      </div>
      <div className="h-[420px] overflow-hidden rounded-[1.5rem] border border-slate-800">
        <MapContainer center={center} zoom={5} className="h-full w-full">
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {trucks.map((truck, index) => {
            const position = normalizePosition(truck, index);
            const status = truck.status?.toLowerCase().includes('delay')
              ? truck.status?.toLowerCase().includes('critical')
                ? 'critical_delay'
                : 'slight_delay'
              : 'on_time';
            return (
              <CircleMarker
                key={truck.transport_id || index}
                center={position}
                pathOptions={{ color: statusColor[status], fillColor: statusColor[status], fillOpacity: 0.8 }}
                radius={12}
              >
                <Popup>
                  <div className="space-y-1 text-slate-900">
                    <p className="font-semibold">{truck.transport_id || `Truck ${index + 1}`}</p>
                    <p className="text-sm">{truck.status || 'On time'}</p>
                    <p className="text-sm">ETA: {truck.eta_hours?.toFixed(1) ?? '—'}h</p>
                    <p className="text-sm">Distance: {truck.distance_remaining ?? '—'} km</p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}
