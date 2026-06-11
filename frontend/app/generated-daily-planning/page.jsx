"use client";

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { AlertTriangle, CalendarDays, Package, Plus, RefreshCcw, Wand2 } from 'lucide-react';
import { exportDailyPlan, generateDailyPlan } from '../services/api';
import AddDeliveryModal from '../../components/planning/AddDeliveryModal';
import ConstraintsPanel from '../../components/planning/ConstraintsPanel';
import ExportButton from '../../components/planning/ExportButton';
import GanttBoard from '../../components/planning/GanttBoard';
import PlanTable from '../../components/planning/PlanTable';

// Leaflet touches `window` at import time, so load the map client-side only.
const RouteMap = dynamic(() => import('../../components/planning/RouteMap'), { ssr: false });
import { WORK_START, WORK_END, toMinutes, toClock, clampMinute } from '../../components/planning/timeline';
import { trucks as fallbackTrucks } from '../../data/coficabData';
import { useFleet } from '../../hooks/useFleet';
import {
  applyTruckStatusOverrides,
  normalizeTruckStatus,
  UNAVAILABLE_TRUCK_STATUSES,
} from '../../utils/truckStatus';

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function countDeliveries(plan) {
  if (!plan) return 0;
  return (plan.trucks || []).reduce((sum, truck) => (
    sum + (truck.trips || []).reduce((tripSum, trip) => tripSum + (trip.stops || []).length, 0)
  ), 0);
}

function countPositions(plan) {
  if (!plan) return 0;
  const assigned = (plan.trucks || []).reduce((sum, truck) => (
    sum + (truck.trips || []).reduce((tripSum, trip) => (
      tripSum + (trip.stops || []).reduce((stopSum, stop) => stopSum + Number(stop.quantity_positions || stop.position_count || 0), 0)
    ), 0)
  ), 0);
  const unassigned = (plan.unassigned || []).reduce((sum, stop) => sum + Number(stop.quantity_positions || stop.position_count || 0), 0);
  return assigned + unassigned;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function mutateDelivery(plan, deliveryId, mapper) {
  if (!plan) return plan;
  return {
    ...plan,
    trucks: plan.trucks.map((truck) => ({
      ...truck,
      trips: truck.trips.map((trip) => ({
        ...trip,
        stops: trip.stops.map((stop) => String(stop.id) === String(deliveryId) ? mapper(stop) : stop),
      })),
    })),
  };
}

function deliveryDuration(delivery) {
  const span = toMinutes(delivery.eta) - toMinutes(delivery.etd);
  return Math.max(30, span || 45);
}

function flattenStops(truck) {
  return (truck.trips || []).flatMap((trip) => trip.stops || []);
}

function findDelivery(plan, deliveryId) {
  for (const truck of plan?.trucks || []) {
    for (const trip of truck.trips || []) {
      for (const stop of trip.stops || []) {
        if (String(stop.id) === String(deliveryId)) {
          return { delivery: stop, truck };
        }
      }
    }
  }
  return { delivery: null, truck: null };
}

function buildLaneTrip(truckId, stops) {
  if (stops.length === 0) return [];
  const sorted = [...stops].sort((a, b) => toMinutes(a.etd) - toMinutes(b.etd));
  const trips = [];
  let current = [];

  sorted.forEach((stop) => {
    const previous = current[current.length - 1];
    if (previous && toMinutes(stop.etd) - toMinutes(previous.eta) > 45) {
      trips.push(current);
      current = [];
    }
    current.push(stop);
  });
  if (current.length) trips.push(current);

  return trips.map((tripStops, index) => {
    const firstStart = toMinutes(tripStops[0].etd);
    const lastEnd = toMinutes(tripStops[tripStops.length - 1].eta);
    return {
      trip_id: `${truckId}-trip-${index + 1}`,
      depart_at: toClock(Math.max(WORK_START, firstStart - 15)),
      return_at: toClock(Math.min(WORK_END, lastEnd + 15)),
      stops: tripStops,
    };
  });
}

function reflowStops(stops, anchorMinute = WORK_START) {
  let cursor = Math.max(WORK_START, anchorMinute);
  return stops.map((stop, index) => {
    const duration = deliveryDuration(stop);
    const preferred = index === 0 ? cursor : Math.max(cursor, toMinutes(stop.etd));
    const start = Math.min(preferred, WORK_END - duration);
    const end = start + duration;
    cursor = end + 15;
    return { ...stop, etd: toClock(start), eta: toClock(end) };
  });
}

function normalizeTruckTrips(truck, anchorMinute = null) {
  const stops = flattenStops(truck).sort((a, b) => toMinutes(a.etd) - toMinutes(b.etd));
  if (stops.length === 0) return { ...truck, trips: [] };
  const firstStart = anchorMinute ?? toMinutes(stops[0].etd);
  return {
    ...truck,
    trips: buildLaneTrip(truck.truck_id, reflowStops(stops, firstStart)),
  };
}

function withManualMarkers(plan) {
  return {
    ...plan,
    manual_markers: plan?.manual_markers || [],
  };
}

function toDailyTruckPayload(truck) {
  const status = normalizeTruckStatus(truck.status);
  if (UNAVAILABLE_TRUCK_STATUSES.has(status)) return null;

  const capacityPositions = Number(truck.capacity_positions ?? truck.max_palettes ?? truck.max_pallets ?? 0);
  const capacityKg = Number(truck.capacity_kg ?? truck.capacite_kg ?? truck.capacity ?? 0);
  if (!capacityPositions) return null;

  return {
    truck_id: truck.id ?? truck.truck_id,
    truck_label: truck.plate_number || truck.truck_label || `Truck ${truck.id ?? truck.truck_id}`,
    capacity_positions: capacityPositions,
    capacity_kg: capacityKg,
  };
}

export default function GeneratedDailyPlanningPage() {
  const { trucks: apiTrucks } = useFleet();
  // Start empty so server and client first-render match; the real date is set
  // after mount (avoids a Date-driven hydration mismatch).
  const [day, setDay] = useState('');
  const [plan, setPlan] = useState(null);
  // Start in the loading state so the drag-and-drop board (which generates
  // non-deterministic @dnd-kit accessibility ids) is never server-rendered —
  // this avoids an aria-describedby hydration mismatch. Data is fetched on mount.
  const [status, setStatus] = useState('generating');
  const [error, setError] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [selectedTruckId, setSelectedTruckId] = useState(null);

  const stats = useMemo(() => ({
    deliveries: countDeliveries(plan),
    positions: countPositions(plan),
    trucks: plan?.trucks?.filter((truck) => (truck.trips || []).length > 0).length || 0,
    unassigned: plan?.unassigned?.length || 0,
  }), [plan]);

  const activeTrucks = useMemo(() => (
    applyTruckStatusOverrides(apiTrucks.length ? apiTrucks : fallbackTrucks)
      .map(toDailyTruckPayload)
      .filter(Boolean)
  ), [apiTrucks]);

  async function regenerate(nextDay = day) {
    setStatus('generating');
    setError(null);
    try {
      const nextPlan = await generateDailyPlan(nextDay, undefined, activeTrucks);
      setPlan(withManualMarkers(nextPlan));
      setStatus('ready');
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to generate the daily plan.');
      setStatus('ready');
    }
  }

  useEffect(() => {
    const initial = todayIso();
    setDay(initial);
    regenerate(initial);
  }, []);

  function moveDelivery(deliveryId, targetTruckId, targetMinute = WORK_START) {
    if (!deliveryId || !plan) return;
    let moved = null;
    const sourceCleared = {
      ...plan,
      trucks: plan.trucks.map((truck) => ({
        ...truck,
        trips: truck.trips.map((trip) => {
          const remaining = trip.stops.filter((stop) => {
            if (String(stop.id) === String(deliveryId)) {
              moved = stop;
              return false;
            }
            return true;
          });
          return { ...trip, stops: remaining };
        }).filter((trip) => trip.stops.length > 0),
      })),
    };
    if (!moved) return;

    const duration = deliveryDuration(moved);
    const normalizedTargetMinute = clampMinute(targetMinute, WORK_START, WORK_END - duration);
    const requiredTruck = moved.constraints?.required_truck_id;
    if (requiredTruck && String(requiredTruck) !== String(targetTruckId)) {
      setError(`${moved.client} is fixed to Truck ${requiredTruck}.`);
      return;
    }

    const timeWindow = moved.constraints?.time_window;
    if (timeWindow?.length === 2) {
      const windowStart = toMinutes(timeWindow[0]);
      const windowEnd = toMinutes(timeWindow[1]);
      const movedEnd = normalizedTargetMinute + duration;
      if (normalizedTargetMinute < windowStart || movedEnd > windowEnd) {
        setError(`${moved.client} must stay between ${timeWindow[0]} and ${timeWindow[1]}.`);
        return;
      }
    }

    setError(null);
    setPlan({
      ...sourceCleared,
      trucks: sourceCleared.trucks.map((truck) => {
        const stops = flattenStops(truck).sort((a, b) => toMinutes(a.etd) - toMinutes(b.etd));
        if (String(truck.truck_id) !== String(targetTruckId)) {
          return normalizeTruckTrips({ ...truck, trips: buildLaneTrip(truck.truck_id, stops) });
        }

        const movedWithTarget = { ...moved, etd: toClock(normalizedTargetMinute), eta: toClock(normalizedTargetMinute + duration) };
        return normalizeTruckTrips(
          { ...truck, trips: buildLaneTrip(truck.truck_id, [...stops, movedWithTarget]) },
          Math.min(normalizedTargetMinute, toMinutes(stops[0]?.etd || movedWithTarget.etd)),
        );
      }),
    });
  }

  function resizeDelivery(deliveryId, nextEtd, nextEta) {
    if (!deliveryId || !plan) return;
    const { delivery } = findDelivery(plan, deliveryId);
    if (!delivery) return;

    let nextStart = clampMinute(toMinutes(nextEtd));
    let nextEnd = clampMinute(toMinutes(nextEta));
    if (nextEnd - nextStart < 30) {
      nextEnd = clampMinute(nextStart + 30);
      nextStart = clampMinute(nextEnd - 30);
    }

    const timeWindow = delivery.constraints?.time_window;
    if (timeWindow?.length === 2) {
      const windowStart = toMinutes(timeWindow[0]);
      const windowEnd = toMinutes(timeWindow[1]);
      if (nextStart < windowStart || nextEnd > windowEnd) {
        setError(`${delivery.client} must stay between ${timeWindow[0]} and ${timeWindow[1]}.`);
        return;
      }
    }

    setError(null);
    setPlan({
      ...plan,
      trucks: plan.trucks.map((truck) => {
        const stops = flattenStops(truck).map((stop) => (
          String(stop.id) === String(deliveryId)
            ? { ...stop, etd: toClock(nextStart), eta: toClock(nextEnd) }
            : stop
        ));
        return normalizeTruckTrips({ ...truck, trips: buildLaneTrip(truck.truck_id, stops) });
      }),
    });
  }

  function cancelDelivery(deliveryId) {
    setPlan((current) => mutateDelivery(current, deliveryId, (stop) => ({ ...stop, status: 'cancelled' })));
  }

  function restoreDelivery(deliveryId) {
    setPlan((current) => mutateDelivery(current, deliveryId, (stop) => ({ ...stop, status: 'planned' })));
  }

  function addDelivery(form) {
    const delivery = {
      id: Date.now(),
      client: form.client || 'New delivery',
      start_location: 'COFICAB Megrine',
      end_location: form.client || 'New delivery',
      quantity_positions: form.quantity_positions,
      position_count: form.quantity_positions,
      quantity_kg: form.quantity_kg || 0,
      etd: form.etd,
      eta: form.eta,
      priority: form.priority,
      status: 'new',
      constraints: { required_date: day },
      raw: {},
    };
    setPlan((current) => ({
      ...current,
      trucks: current.trucks.map((truck) => {
        if (String(truck.truck_id) !== String(form.truck_id)) return truck;
        const stops = flattenStops(truck);
        const reflowed = reflowStops([...stops, delivery].sort((a, b) => toMinutes(a.etd) - toMinutes(b.etd)), toMinutes(stops[0]?.etd || delivery.etd));
        return {
          ...truck,
          trips: buildLaneTrip(truck.truck_id, reflowed),
        };
      }),
    }));
  }

  function addMarker(targetTruckId, targetMinute) {
    setPlan((current) => {
      if (!current) return current;
      return {
        ...current,
        manual_markers: [
          ...(current.manual_markers || []),
          {
            id: `marker-${Date.now()}`,
            truck_id: targetTruckId,
            time: toClock(clampMinute(targetMinute, WORK_START, WORK_END)),
            label: 'Manual marker',
          },
        ],
      };
    });
  }

  function moveMarker(markerId, targetTruckId, targetMinute) {
    setPlan((current) => {
      if (!current) return current;
      return {
        ...current,
        manual_markers: (current.manual_markers || []).map((marker) => (
          String(marker.id) === String(markerId)
            ? { ...marker, truck_id: targetTruckId, time: toClock(clampMinute(targetMinute, WORK_START, WORK_END)) }
            : marker
        )),
      };
    });
  }

  function deleteMarker(markerId) {
    setPlan((current) => {
      if (!current) return current;
      return {
        ...current,
        manual_markers: (current.manual_markers || []).filter((marker) => String(marker.id) !== String(markerId)),
      };
    });
  }

  async function handleExport() {
    if (!plan?.source_file) {
      setError('No source workbook is loaded yet.');
      return;
    }
    setExporting(true);
    setError(null);
    try {
      const result = await exportDailyPlan({ source_file: plan.source_file, day, plan });
      window.location.href = result.download_url;
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to export the edited workbook.');
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f7f3] p-8">
      <motion.div initial="hidden" animate="show" className="space-y-8">
        <motion.div variants={item} className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Generated Daily Planning</p>
            <h1 className="mt-3 text-3xl font-semibold text-[#1a1a2e]">Truck timeline editor</h1>
            <p className="mt-2 text-sm text-[#6b6b7b]">
              Auto-generated from {plan?.source_file || 'weekly planning'} {plan?.generated_at ? `at ${new Date(plan.generated_at).toLocaleTimeString()}` : ''}
            </p>
            {plan?.selection && (
              <p className="mt-1 text-xs text-[#6b6b7b]">
                Using {plan.selection.matched_day || plan.selection.requested_day} rows from the workbook for {plan.selection.requested_date}.
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-4 py-2 text-sm font-semibold text-[#1a1a2e]">
              <CalendarDays size={16} />
              <input
                type="date"
                value={day}
                onChange={(event) => {
                  setDay(event.target.value);
                  regenerate(event.target.value);
                }}
                className="bg-transparent outline-none"
              />
            </label>
            <button
              type="button"
              onClick={() => regenerate(day)}
              disabled={status === 'generating'}
              className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-5 py-2 text-sm font-semibold text-[#1a1a2e] transition hover:bg-[#faf8f5] disabled:opacity-60"
            >
              <RefreshCcw size={16} />
              Regenerate
            </button>
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              disabled={!plan || status === 'generating'}
              className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-5 py-2 text-sm font-semibold text-[#1a1a2e] transition hover:bg-[#faf8f5] disabled:opacity-60"
            >
              <Plus size={16} />
              Add delivery
            </button>
            <ExportButton exporting={exporting} disabled={!plan?.source_file || status === 'generating'} onExport={handleExport} />
          </div>
        </motion.div>

        {plan?.selection?.fallback && (
          <div className="flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            <AlertTriangle size={16} />
            No {plan.selection.requested_day} rows were found, so the planner is showing {plan.selection.matched_day || 'the first available day'}.
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertTriangle size={16} />
            {error}
          </div>
        )}

        <motion.div variants={item} className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ['Deliveries', stats.deliveries, Wand2],
            ['Positions', stats.positions, Package],
            ['Active trucks', stats.trucks, CalendarDays],
            ['Unassigned', stats.unassigned, AlertTriangle],
          ].map(([label, value, Icon]) => (
            <div key={label} className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
              <div className="mb-4 inline-flex rounded-2xl bg-[#7c3aed]/10 p-3 text-[#7c3aed]"><Icon size={18} /></div>
              <p className="text-sm uppercase tracking-[0.18em] text-[#6b6b7b]">{label}</p>
              <p className="mt-2 text-3xl font-semibold text-[#1a1a2e]">{status === 'generating' ? '--' : formatNumber(value)}</p>
            </div>
          ))}
        </motion.div>

        {(plan?.unassigned || []).length > 0 && (
          <div className="rounded-[1.75rem] border border-red-200 bg-red-50 p-5">
            <div className="mb-3 flex items-center gap-2 text-red-700">
              <AlertTriangle size={16} />
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em]">Needs dispatcher review</h2>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {plan.unassigned.map((delivery) => (
                <div key={delivery.id} className="rounded-2xl border border-red-200 bg-white p-4">
                  <p className="font-semibold text-[#1a1a2e]">{delivery.client}</p>
                  <p className="mt-1 text-xs text-[#6b6b7b]">
                    {formatNumber(delivery.quantity_positions || delivery.position_count)} positions
                    {delivery.quantity_kg ? ` - ${formatNumber(delivery.quantity_kg)} kg` : ''}
                  </p>
                  {delivery.constraints?.comment_constraint && (
                    <p className="mt-2 inline-flex items-start gap-1 rounded-lg bg-amber-50 px-2 py-1 text-xs text-amber-800 ring-1 ring-amber-200">
                      <span className="font-semibold uppercase tracking-wide">Note</span>
                      <span className="font-medium">{delivery.constraints.comment_constraint}</span>
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
          {status === 'generating' && !plan ? (
            <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-8 shadow-sm">
              <div className="h-96 rounded-2xl bg-[#f0eee9] animate-pulse" />
            </div>
          ) : (
            // Wrap in a single grid cell: GanttBoard's <DndContext> renders
            // several sibling nodes (marker toolbar, the scroller, and dnd-kit's
            // hidden a11y live regions). Without this wrapper those siblings are
            // auto-placed as separate grid items and the timeline gets squeezed
            // into the narrow side column. min-w-0 lets the scroller shrink so
            // its 1800px content stays inside the cell and scrolls horizontally.
            <div className="min-w-0">
              <GanttBoard
                plan={plan}
                selectedTruckId={selectedTruckId}
                onSelectTruck={setSelectedTruckId}
                onDropDelivery={moveDelivery}
                onResizeDelivery={resizeDelivery}
                onCancel={cancelDelivery}
                onRestore={restoreDelivery}
                onDropMarker={addMarker}
                onMoveMarker={moveMarker}
                onDeleteMarker={deleteMarker}
              />
            </div>
          )}
          <ConstraintsPanel plan={plan} onRestore={restoreDelivery} />
        </div>

        {plan && (
          <RouteMap
            plan={plan}
            selectedTruckId={selectedTruckId}
            onSelectTruck={setSelectedTruckId}
          />
        )}

        {plan && (
          <PlanTable
            plan={plan}
            exporting={exporting}
            onExport={plan?.source_file ? handleExport : null}
          />
        )}
      </motion.div>

      <AddDeliveryModal
        open={modalOpen}
        trucks={plan?.trucks || []}
        onClose={() => setModalOpen(false)}
        onAdd={addDelivery}
      />
    </div>
  );
}
