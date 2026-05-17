"use client";

import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const markerColor = '#0ea5e9';
const markerAccent = '#0284c7';

function normalizePosition(client, index) {
  if (client.lat && client.lng) {
    return [client.lat, client.lng];
  }
  const base = 36.8 + (index % 5) * 0.08;
  return [base, 10.1 + (index % 7) * 0.09];
}

export default function ClientMap({ clients = [] }) {
  const center = clients.length ? normalizePosition(clients[0], 0) : [36.806, 10.181];

  return (
    <div className="rounded-[2rem] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-xl shadow-black/10">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm text-[var(--muted)]">Client distribution</p>
          <h3 className="text-xl font-semibold text-[var(--text)]">Client delivery map</h3>
        </div>
      </div>
      <div className="h-[420px] overflow-hidden rounded-[1.5rem] border border-[var(--border)]">
        <MapContainer center={center} zoom={6} className="h-full w-full">
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {clients.map((client, index) => {
            const position = normalizePosition(client, index);
            return (
              <CircleMarker
                key={client.id || index}
                center={position}
                pathOptions={{ color: markerColor, fillColor: markerAccent, fillOpacity: 0.8 }}
                radius={10}
              >
                <Popup>
                  <div className="space-y-1 text-slate-900">
                    <p className="font-semibold">{client.customer}</p>
                    <p className="text-sm">Destination: {client.destination}</p>
                    <p className="text-sm">Distance: {client.km} km</p>
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
