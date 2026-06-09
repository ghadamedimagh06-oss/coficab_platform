"use client";

import { Clock, MapPinned, Route, Timer } from 'lucide-react';

function number(value, digits = 0) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '--';
  return numeric.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function routeTrips(plan) {
  return (plan?.trucks || []).flatMap((truck) => (
    (truck.trips || []).map((trip) => ({ ...trip, truck_label: truck.truck_label, truck_id: truck.truck_id }))
  )).filter((trip) => (trip.stops || []).length > 0);
}

export function getRouteTotals(plan) {
  const trips = routeTrips(plan);
  const routed = trips.filter((trip) => trip.total_distance_km != null && trip.total_travel_min != null);
  return {
    trips: trips.length,
    routedTrips: routed.length,
    distanceKm: routed.reduce((sum, trip) => sum + Number(trip.total_distance_km || 0), 0),
    travelMin: routed.reduce((sum, trip) => sum + Number(trip.total_travel_min || 0), 0),
    serviceMin: routed.reduce((sum, trip) => sum + Number(trip.total_service_min || 0), 0),
    pendingTrips: trips.length - routed.length,
  };
}

export default function RouteSummary({ plan }) {
  if (!plan) return null;

  const totals = getRouteTotals(plan);
  const totalDuration = totals.travelMin + totals.serviceMin;
  const cards = [
    { label: 'OSRM distance', value: `${number(totals.distanceKm, 1)} km`, icon: Route },
    { label: 'Travel time', value: `${number(totals.travelMin)} min`, icon: Clock },
    { label: 'Service time', value: `${number(totals.serviceMin)} min`, icon: Timer },
    { label: 'Total route time', value: `${number(totalDuration)} min`, icon: MapPinned },
  ];

  return (
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map(({ label, value, icon: Icon }) => (
        <div key={label} className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
          <div className="mb-3 inline-flex rounded-2xl bg-[#0f766e]/10 p-2.5 text-[#0f766e]">
            <Icon size={17} />
          </div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#6b6b7b]">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-[#1a1a2e]">{value}</p>
        </div>
      ))}
      {totals.pendingTrips > 0 && (
        <div className="sm:col-span-2 xl:col-span-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-700">
          {totals.pendingTrips} trip{totals.pendingTrips === 1 ? '' : 's'} need backend route recalculation after manual edits.
        </div>
      )}
    </section>
  );
}
