"use client";

import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const statusColor = {
  on_time: '#22c55e',
  slight_delay: '#f59e0b',
  critical_delay: '#ef4444',
};

const clientColor = '#38bdf8';
const clientAccent = '#0ea5e9';
const tunisiaCenter = [35.8, 9.6];

function normalizePosition(entity, index) {
  if (entity.lat && entity.lng) {
    return [entity.lat, entity.lng];
  }
  if (entity.latitude && entity.longitude) {
    return [entity.latitude, entity.longitude];
  }
  const base = 36.806 + (index % 5) * 0.08;
  return [base, 10.181 + (index % 7) * 0.09];
}

function getMapCenter(trucks, clients) {
  const points = [...trucks, ...clients].map((item, index) => normalizePosition(item, index));
  if (!points.length) {
    return tunisiaCenter;
  }
  const sum = points.reduce(
    (acc, [lat, lng]) => {
      acc.lat += lat;
      acc.lng += lng;
      return acc;
    },
    { lat: 0, lng: 0 }
  );
  return [sum.lat / points.length, sum.lng / points.length];
}

export default function TruckMap({ trucks = [], clients = [], height = 420, hideHeader = false }) {
  const [isClient, setIsClient] = useState(false);
  
  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    return (
      <div 
        className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-4 shadow-xl shadow-black/20"
        style={{ height: height ? height + 40 : 460 }}
      >
        <div className="h-full w-full bg-slate-900 rounded-[1.5rem] flex items-center justify-center">
          <p className="text-slate-400">Loading map...</p>
        </div>
      </div>
    );
  }

  const center = getMapCenter(trucks, clients);

  return (
    <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-4 shadow-xl shadow-black/20">
      {!hideHeader && (
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-400">Real-time positions</p>
            <h3 className="text-xl font-semibold">Live truck map</h3>
          </div>
        </div>
      )}
      <div className="overflow-hidden rounded-[1.5rem] border border-slate-800" style={{ height }}>
        <MapContainer center={center} zoom={6} className="h-full w-full" key={`map-${JSON.stringify(center)}`}>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {clients.map((client, index) => {
            const position = normalizePosition(client, index);
            return (
              <CircleMarker
                key={client.id || `client-${index}`}
                center={position}
                pathOptions={{ color: clientColor, fillColor: clientAccent, fillOpacity: 0.7 }}
                radius={8}
              >
                <Popup>
                  <div className="space-y-1 text-slate-900">
                    <p className="font-semibold">{client.customer}</p>
                    <p className="text-sm">Destination: {client.destination}</p>
                    <p className="text-sm">Distance: {client.km ?? '—'} km</p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
          {trucks.map((truck, index) => {
            const position = normalizePosition(truck, index);
            const status = truck.status?.toLowerCase().includes('delay')
              ? truck.status?.toLowerCase().includes('critical')
                ? 'critical_delay'
                : 'slight_delay'
              : 'on_time';
            return (
              <CircleMarker
                key={truck.transport_id || truck.id || `truck-${index}`}
                center={position}
                pathOptions={{ color: statusColor[status], fillColor: statusColor[status], fillOpacity: 0.8 }}
                radius={12}
              >
                <Popup>
                  <div className="space-y-1 text-slate-900">
                    <p className="font-semibold">{truck.transport_id || truck.id || `Truck ${index + 1}`}</p>
                    <p className="text-sm">{truck.status || 'On time'}</p>
                    <p className="text-sm">ETA: {truck.eta_hours?.toFixed(1) ?? '—'}h</p>
                    <p className="text-sm">Distance: {truck.distance_remaining ?? truck.km ?? '—'} km</p>
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
