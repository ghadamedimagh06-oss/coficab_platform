"use client";

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const tunisiaCenter = [35.8, 9.6];
const palette = ['#0f766e', '#7c3aed', '#dc2626', '#2563eb', '#f97316', '#16a34a', '#9333ea'];

function geometryPoints(geometry) {
  const coords = geometry?.coordinates;
  if (!Array.isArray(coords)) return [];
  return coords
    .filter((point) => Array.isArray(point) && point.length >= 2)
    .map(([lon, lat]) => [lat, lon]);
}

function stopPoint(stop) {
  const lat = Number(stop.lat);
  const lon = Number(stop.lon ?? stop.lng);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return [lat, lon];
}

function collectRoutes(plan) {
  return (plan?.trucks || []).flatMap((truck, truckIndex) => (
    (truck.trips || []).map((trip, tripIndex) => ({
      id: `${truck.truck_id}-${trip.trip_id}`,
      label: `${truck.truck_label || `Truck ${truck.truck_id}`} / ${trip.trip_id}`,
      color: palette[(truckIndex + tripIndex) % palette.length],
      points: geometryPoints(trip.geometry),
      stops: trip.stops || [],
      distance: trip.total_distance_km,
      travel: trip.total_travel_min,
    }))
  )).filter((route) => route.points.length > 1);
}

function collectBounds(routes) {
  return routes.flatMap((route) => [
    ...route.points,
    ...route.stops.map(stopPoint).filter(Boolean),
  ]);
}

function FitBounds({ routes }) {
  const map = useMap();
  useEffect(() => {
    const bounds = collectBounds(routes);
    if (bounds.length > 1) {
      map.fitBounds(bounds, { padding: [24, 24], maxZoom: 10 });
    }
  }, [map, routes]);
  return null;
}

export default function RouteMap({ plan }) {
  const [isClient, setIsClient] = useState(false);
  const routes = useMemo(() => collectRoutes(plan), [plan]);

  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!plan || !routes.length) return null;

  if (!isClient) {
    return (
      <section className="rounded-[2rem] border border-[#e8e5df] bg-white p-4 shadow-sm">
        <div className="h-[360px] rounded-[1.5rem] bg-[#f0eee9]" />
      </section>
    );
  }

  return (
    <section className="rounded-[2rem] border border-[#e8e5df] bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#0f766e]">OSRM routes</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1a1a2e]">Road itinerary map</h2>
        </div>
      </div>
      <div className="h-[360px] overflow-hidden rounded-[1.5rem] border border-[#e8e5df]">
        <MapContainer center={tunisiaCenter} zoom={6} className="h-full w-full" scrollWheelZoom={false}>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitBounds routes={routes} />
          {routes.map((route) => (
            <Polyline
              key={route.id}
              positions={route.points}
              pathOptions={{ color: route.color, weight: 4, opacity: 0.85 }}
            >
              <Popup>
                <div className="space-y-1 text-slate-900">
                  <p className="font-semibold">{route.label}</p>
                  <p className="text-sm">{route.distance?.toFixed?.(1) ?? route.distance} km</p>
                  <p className="text-sm">{route.travel} min travel</p>
                </div>
              </Popup>
            </Polyline>
          ))}
          {routes.flatMap((route) => route.stops.map((stop, index) => {
            const point = stopPoint(stop);
            if (!point) return null;
            return (
              <CircleMarker
                key={`${route.id}-${stop.id}-${index}`}
                center={point}
                pathOptions={{ color: route.color, fillColor: route.color, fillOpacity: 0.85 }}
                radius={6}
              >
                <Popup>
                  <div className="space-y-1 text-slate-900">
                    <p className="font-semibold">{stop.client}</p>
                    <p className="text-sm">{stop.etd} - {stop.eta}</p>
                    <p className="text-sm">{stop.distance_km ?? '--'} km leg</p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          }))}
        </MapContainer>
      </div>
    </section>
  );
}
