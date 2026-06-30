"use client";

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, CalendarDays, Package, Plus, RefreshCcw, ShieldCheck, ShieldOff, Wand2 } from 'lucide-react';
import { approveDailyRental, exportDailyPlan, generateDailyPlan, recalculateDailyPlan } from '../services/api';
import AddDeliveryModal from '../../components/planning/AddDeliveryModal';
import ExportButton from '../../components/planning/ExportButton';
import GanttBoard from '../../components/planning/GanttBoard';
import JustificationModal from '../../components/planning/JustificationModal';
import PlanChangeLog from '../../components/planning/PlanChangeLog';
import PlanTable from '../../components/planning/PlanTable';
import StressTestPanel from '../../components/planning/StressTestPanel';
import ConfidencePanel from '../../components/planning/ConfidencePanel';
import DisruptionPanel from '../../components/planning/DisruptionPanel';
import ExplainPanel from '../../components/planning/ExplainPanel';
import ControlTowerPanel from '../../components/planning/ControlTowerPanel';
import { WORK_START, WORK_END, toMinutes, toClock, clampMinute } from '../../components/planning/timeline';
import { useDrivers, useFleet } from '../../hooks/useFleet';
import {
  applyDriverStatusOverrides,
  applyTruckAssignmentOverrides,
  applyTruckStatusOverrides,
  normalizeDriverStatus,
  normalizeTruckStatus,
  UNAVAILABLE_DRIVER_STATUSES,
  UNAVAILABLE_TRUCK_STATUSES,
} from '../../utils/truckStatus';

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

// ── Plan cache ────────────────────────────────────────────────────────────
// Generating a daily plan is a ~6s backend call (live Nominatim + OSRM road
// matrix). Without caching, every reload or navigation back to this page paid
// that cost again. We cache the (possibly edited) plan per day in two layers:
//   • an in-memory Map that survives client-side navigation within the SPA, and
//   • sessionStorage so a full page reload restores instantly too.
// The Regenerate button bypasses the cache to force a fresh build.
const PLAN_MEMORY_CACHE = new Map();
const CACHE_PREFIX = 'coficab:dailyPlan:';

function cacheKey(day, resourceSignature) {
  return `${CACHE_PREFIX}${day}:${resourceSignature || 'resources'}`;
}

function readCachedPlan(day, resourceSignature) {
  if (!day) return null;
  const key = cacheKey(day, resourceSignature);
  if (PLAN_MEMORY_CACHE.has(key)) return PLAN_MEMORY_CACHE.get(key);
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    PLAN_MEMORY_CACHE.set(key, parsed);
    return parsed;
  } catch {
    return null;
  }
}

function writeCachedPlan(day, resourceSignature, plan) {
  if (!day || !plan) return;
  const key = cacheKey(day, resourceSignature);
  PLAN_MEMORY_CACHE.set(key, plan);
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(key, JSON.stringify(plan));
  } catch {
    // Quota or serialization issue — the in-memory cache still covers navigation.
  }
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
  // Also look among the unassigned deliveries (no source truck).
  for (const stop of plan?.unassigned || []) {
    if (String(stop.id) === String(deliveryId)) {
      return { delivery: stop, truck: null };
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

function normalizeResourceDriver(driver) {
  const id = driver.id;
  return {
    ...driver,
    id,
    full_name: driver.full_name,
    status: normalizeDriverStatus(driver.status),
    assigned_truck: driver.assigned_truck ?? driver.camion_defaut_id ?? null,
  };
}

function toDailyTruckPayload(truck, driverById, drivers) {
  const status = normalizeTruckStatus(truck.status);
  const truckId = truck.id ?? truck.truck_id;
  const assignedDriver = (
    truck.assigned_driver
    ?? truck.chauffeur_defaut_id
    ?? drivers.find((candidate) => String(candidate.assigned_truck) === String(truckId))?.id
    ?? null
  );
  const driver = assignedDriver != null ? driverById[String(assignedDriver)] : null;
  const capacityPositions = Number(truck.capacity_positions ?? truck.max_palettes ?? truck.max_pallets ?? 0);
  const capacityKg = Number(truck.capacity_kg ?? truck.capacite_kg ?? truck.capacity ?? 0);
  if (!capacityPositions) return null;

  const truckUnavailable = UNAVAILABLE_TRUCK_STATUSES.has(status);
  const hasAssignedDriver = assignedDriver != null && assignedDriver !== '';
  const driverUnavailable = !hasAssignedDriver || (
    driver && (UNAVAILABLE_DRIVER_STATUSES.has(driver.status) || driver.status === 'En pause')
  );
  const outOfServiceReason = truckUnavailable
    ? status
    : driverUnavailable
      ? (driver ? `Driver ${driver.status}` : 'No assigned driver')
      : null;

  return {
    truck_id: truckId,
    truck_label: truck.plate_number || truck.truck_label || `Truck ${truckId}`,
    capacity_positions: capacityPositions,
    capacity_kg: capacityKg,
    capacity_m3: truck.capacity_m3,
    driver_id: driver?.id ?? assignedDriver ?? null,
    driver: driver?.full_name ?? null,
    resource_status: outOfServiceReason ? 'out_of_service' : 'available',
    resource_reason: outOfServiceReason,
    truck_status: status,
  };
}

function withResourceLanes(plan, resourceFleet) {
  if (!plan) return plan;
  const byId = new Map((resourceFleet || []).map((truck) => [String(truck.truck_id), truck]));
  const enriched = (plan.trucks || []).map((truck) => ({
    ...truck,
    ...(byId.get(String(truck.truck_id)) || {}),
    trips: truck.trips || [],
  }));
  const plannedIds = new Set(enriched.map((truck) => String(truck.truck_id)));
  const unavailable = (resourceFleet || [])
    .filter((truck) => truck.resource_status === 'out_of_service' && !plannedIds.has(String(truck.truck_id)))
    .map((truck) => ({ ...truck, trips: [] }));
  return {
    ...plan,
    trucks: [...enriched, ...unavailable],
    resource_summary: {
      total: resourceFleet.length,
      available: resourceFleet.filter((truck) => truck.resource_status !== 'out_of_service').length,
      out_of_service: resourceFleet.filter((truck) => truck.resource_status === 'out_of_service').length,
    },
  };
}

function resourceSignature(resourceFleet) {
  return JSON.stringify((resourceFleet || []).map((truck) => ({
    id: truck.truck_id,
    status: truck.resource_status,
    reason: truck.resource_reason,
    driver: truck.driver_id,
  })));
}

export default function GeneratedDailyPlanningPage() {
  const { trucks: apiTrucks, isLoading: trucksLoading, error: fleetError } = useFleet();
  const { drivers: apiDrivers, isLoading: driversLoading, error: driversError } = useDrivers();
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
  const [isVerified, setIsVerified] = useState(false);
  const [changeLog, setChangeLog] = useState([]);
  const [pendingAction, setPendingAction] = useState(null);

  const stats = useMemo(() => ({
    deliveries: countDeliveries(plan),
    positions: countPositions(plan),
    trucks: plan?.trucks?.filter((truck) => (truck.trips || []).length > 0).length || 0,
    unassigned: plan?.unassigned?.length || 0,
  }), [plan]);

  const resourceReady = !trucksLoading && !driversLoading;

  const resourceFleet = useMemo(() => {
    const drivers = applyDriverStatusOverrides(apiDrivers.map(normalizeResourceDriver));
    const driverById = Object.fromEntries(drivers.map((driver) => [String(driver.id), driver]));
    return applyTruckAssignmentOverrides(applyTruckStatusOverrides(apiTrucks))
      .map((truck) => toDailyTruckPayload(truck, driverById, drivers))
      .filter(Boolean)
      .sort((a, b) => Number(a.truck_id) - Number(b.truck_id));
  }, [apiDrivers, apiTrucks]);

  const activeTrucks = useMemo(
    () => resourceFleet.filter((truck) => truck.resource_status !== 'out_of_service'),
    [resourceFleet],
  );
  const planningTrucks = activeTrucks.length > 0 ? activeTrucks : undefined;
  const currentResourceSignature = useMemo(() => resourceSignature(resourceFleet), [resourceFleet]);

  async function regenerate(nextDay = day) {
    setStatus('generating');
    setError(null);
    try {
      const generated = await generateDailyPlan(nextDay, undefined, planningTrucks);
      const nextPlan = withManualMarkers(withResourceLanes(generated, resourceFleet));
      setPlan(nextPlan);
      writeCachedPlan(nextDay, currentResourceSignature, nextPlan);
      setStatus('ready');
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to generate the daily plan.');
      setStatus('ready');
    }
  }

  async function approveRental(recommendation) {
    if (!recommendation?.truck || !plan) return;
    setStatus('generating');
    setError(null);
    try {
      const basePlanId = String(plan.rental_base_plan_id || plan.plan_id);
      const approval = await approveDailyRental({
        plan_id: basePlanId,
        day,
        recommendation_id: recommendation.id,
        rental_profile: recommendation.profile,
        estimated_cost_eur: recommendation.estimated_cost_eur,
      });
      const approvalIds = [...new Set([...(plan.rental_approval_ids || []), approval.approval_id])];
      const generated = await generateDailyPlan(day, plan.source_file, planningTrucks, approvalIds, basePlanId);
      setPlan(withManualMarkers(withResourceLanes(generated, resourceFleet)));
      setStatus('ready');
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to approve the rental option.');
      setStatus('ready');
    }
  }

  async function applyRecalculatedPlan(nextPlan) {
    setPlan(withManualMarkers(nextPlan));
    setStatus('recalculating');
    try {
      const recalculated = await recalculateDailyPlan(withManualMarkers(nextPlan));
      setPlan(withManualMarkers(withResourceLanes(recalculated, resourceFleet)));
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to recalculate the route with OSRM.');
    } finally {
      setStatus('ready');
    }
  }

  // Show a cached plan instantly when one exists for `nextDay`; only fall back
  // to the slow backend build on a cache miss. Returns true when served cached.
  function showCachedOrRegenerate(nextDay) {
    if (!resourceReady) return false;
    const cached = readCachedPlan(nextDay, currentResourceSignature);
    if (cached) {
      setPlan(withManualMarkers(withResourceLanes(cached, resourceFleet)));
      setError(null);
      setStatus('ready');
      return true;
    }
    regenerate(nextDay);
    return false;
  }

  useEffect(() => {
    const initial = todayIso();
    setDay(initial);
  }, []);

  useEffect(() => {
    if (!day || !resourceReady) return;
    if (fleetError || driversError) {
      setError('Unable to load the persisted fleet and drivers. Planning was not generated with fallback vehicles.');
      setStatus('ready');
      return;
    }
    showCachedOrRegenerate(day);
  }, [day, resourceReady, currentResourceSignature, fleetError, driversError]);

  // Keep the cache in step with local edits (moves, adds, deletes) so a reload
  // restores the latest state rather than the pristine generated plan.
  useEffect(() => {
    if (plan && status === 'ready' && day) writeCachedPlan(day, currentResourceSignature, plan);
  }, [plan, status, day, currentResourceSignature]);

  function moveDelivery(deliveryId, targetTruckId, targetMinute = WORK_START) {
    if (!deliveryId || !plan) return;

    if (isVerified) {
      const { delivery: d, truck: sourceTruck } = findDelivery(plan, deliveryId);
      const targetTruck = plan.trucks.find((t) => String(t.truck_id) === String(targetTruckId));
      const duration = d ? deliveryDuration(d) : 45;
      const clamped = clampMinute(targetMinute, WORK_START, WORK_END - duration);
      setPendingAction({
        action: 'Move',
        description: `Move "${d?.client}" from ${sourceTruck?.truck_label || 'Unassigned'} to ${targetTruck?.truck_label || '?'}`,
        client: d?.client || '?',
        truckFrom: sourceTruck?.truck_label || 'Unassigned',
        truckTo: targetTruck?.truck_label || '?',
        timeFrom: `${d?.etd || '?'}–${d?.eta || '?'}`,
        timeTo: `${toClock(clamped)}–${toClock(clamped + duration)}`,
        execute: () => executeMoveDelivery(deliveryId, targetTruckId, targetMinute),
      });
      return;
    }

    executeMoveDelivery(deliveryId, targetTruckId, targetMinute);
  }

  function executeMoveDelivery(deliveryId, targetTruckId, targetMinute = WORK_START) {
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
      // The delivery may instead be coming from the unassigned tray.
      unassigned: (plan.unassigned || []).filter((stop) => {
        if (String(stop.id) === String(deliveryId)) {
          moved = stop;
          return false;
        }
        return true;
      }),
    };
    if (!moved) return;

    const duration = deliveryDuration(moved);
    const normalizedTargetMinute = clampMinute(targetMinute, WORK_START, WORK_END - duration);
    const requiredTruck = moved.constraints?.required_truck_id;
    if (requiredTruck && String(requiredTruck) !== String(targetTruckId)) {
      setError(`${moved.client} is fixed to Truck ${requiredTruck}.`);
      return;
    }
    const targetTruck = plan.trucks.find((truck) => String(truck.truck_id) === String(targetTruckId));
    if (targetTruck?.resource_status === 'out_of_service') {
      setError(`${targetTruck.truck_label} is out of service (${targetTruck.resource_reason || 'resource unavailable'}).`);
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
    applyRecalculatedPlan({
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

    if (isVerified) {
      const { delivery: d, truck: t } = findDelivery(plan, deliveryId);
      setPendingAction({
        action: 'Reschedule',
        description: `Reschedule "${d?.client}" from ${d?.etd || '?'}–${d?.eta || '?'} to ${nextEtd}–${nextEta}`,
        client: d?.client || '?',
        truckFrom: t?.truck_label || '?',
        truckTo: t?.truck_label || '?',
        timeFrom: `${d?.etd || '?'}–${d?.eta || '?'}`,
        timeTo: `${nextEtd}–${nextEta}`,
        execute: () => executeResizeDelivery(deliveryId, nextEtd, nextEta),
      });
      return;
    }

    executeResizeDelivery(deliveryId, nextEtd, nextEta);
  }

  function executeResizeDelivery(deliveryId, nextEtd, nextEta) {
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
    applyRecalculatedPlan({
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
    if (isVerified) {
      const { delivery: d, truck: t } = findDelivery(plan, deliveryId);
      setPendingAction({
        action: 'Delete',
        description: `Delete delivery "${d?.client}" from ${t?.truck_label || '?'}`,
        client: d?.client || '?',
        truckFrom: t?.truck_label || '?',
        truckTo: 'Removed',
        timeFrom: `${d?.etd || '?'}–${d?.eta || '?'}`,
        timeTo: '—',
        execute: () => executeCancelDelivery(deliveryId),
      });
      return;
    }
    executeCancelDelivery(deliveryId);
  }

  function executeCancelDelivery(deliveryId) {
    setPlan((current) => mutateDelivery(current, deliveryId, (stop) => ({ ...stop, status: 'cancelled' })));
  }

  function restoreDelivery(deliveryId) {
    if (isVerified) {
      const { delivery: d, truck: t } = findDelivery(plan, deliveryId);
      setPendingAction({
        action: 'Restore',
        description: `Restore delivery "${d?.client}" on ${t?.truck_label || '?'}`,
        client: d?.client || '?',
        truckFrom: 'Removed',
        truckTo: t?.truck_label || '?',
        timeFrom: '—',
        timeTo: `${d?.etd || '?'}–${d?.eta || '?'}`,
        execute: () => executeRestoreDelivery(deliveryId),
      });
      return;
    }
    executeRestoreDelivery(deliveryId);
  }

  function executeRestoreDelivery(deliveryId) {
    setPlan((current) => mutateDelivery(current, deliveryId, (stop) => ({ ...stop, status: 'planned' })));
  }

  function addDelivery(form) {
    if (isVerified) {
      const truck = (plan?.trucks || []).find((t) => String(t.truck_id) === String(form.truck_id));
      setPendingAction({
        action: 'Add',
        description: `Add delivery "${form.client || 'New delivery'}" to ${truck?.truck_label || '?'}`,
        client: form.client || 'New delivery',
        truckFrom: 'New',
        truckTo: truck?.truck_label || '?',
        timeFrom: '—',
        timeTo: `${form.etd}–${form.eta}`,
        execute: () => executeAddDelivery(form),
      });
      return;
    }
    executeAddDelivery(form);
  }

  function executeAddDelivery(form) {
    const delivery = {
      id: Date.now(),
      client: form.client || 'New delivery',
      start_location: 'COFICAB Sidi Hassine',
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
    if (!plan) return;
    applyRecalculatedPlan({
      ...plan,
      trucks: plan.trucks.map((truck) => {
        if (String(truck.truck_id) !== String(form.truck_id)) return truck;
        const stops = flattenStops(truck);
        const reflowed = reflowStops([...stops, delivery].sort((a, b) => toMinutes(a.etd) - toMinutes(b.etd)), toMinutes(stops[0]?.etd || delivery.etd));
        return {
          ...truck,
          trips: buildLaneTrip(truck.truck_id, reflowed),
        };
      }),
    });
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

  function confirmPendingAction(reason) {
    if (!pendingAction) return;
    pendingAction.execute();
    setChangeLog((prev) => [
      ...prev,
      {
        id: Date.now(),
        timestamp: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        client: pendingAction.client,
        action: pendingAction.action,
        truckFrom: pendingAction.truckFrom,
        truckTo: pendingAction.truckTo,
        timeFrom: pendingAction.timeFrom,
        timeTo: pendingAction.timeTo,
        reason,
      },
    ]);
    setPendingAction(null);
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
    <div className="min-h-screen bg-canvas p-8">
      <motion.div initial="hidden" animate="show" className="space-y-8">
        <motion.div variants={item} className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-brand-600">Generated Daily Planning</p>
            <h1 className="mt-3 text-3xl font-semibold text-ink">Truck timeline editor</h1>
            <p className="mt-2 text-sm text-muted">
              Auto-generated from {plan?.source_file || 'weekly planning'} {plan?.generated_at ? `at ${new Date(plan.generated_at).toLocaleTimeString()}` : ''}
            </p>
            {status === 'recalculating' && <p className="mt-1 text-xs font-semibold text-teal-700">Recalculating OSRM route legs…</p>}
            {plan?.selection && (
              <p className="mt-1 text-xs text-muted">
                Using {plan.selection.matched_day || plan.selection.requested_day} rows from the workbook for {plan.selection.requested_date}.
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 rounded-full border border-border bg-white px-4 py-2 text-sm font-semibold text-ink">
              <CalendarDays size={16} />
              <input
                type="date"
                value={day}
                onChange={(event) => {
                  setDay(event.target.value);
                  showCachedOrRegenerate(event.target.value);
                }}
                className="bg-transparent outline-none"
              />
            </label>
            <button
              type="button"
              onClick={() => regenerate(day)}
              disabled={status === 'generating' || isVerified}
              title={isVerified ? 'Unlock the plan to regenerate' : 'Fetch a fresh plan from the server (ignores the cached one)'}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-white px-5 py-2 text-sm font-semibold text-ink transition hover:bg-canvas disabled:opacity-60"
            >
              <RefreshCcw size={16} />
              Regenerate
            </button>
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              disabled={!plan || status === 'generating'}
              title={isVerified ? 'Adding a delivery will require a justification' : undefined}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-white px-5 py-2 text-sm font-semibold text-ink transition hover:bg-canvas disabled:opacity-60"
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
            <div key={label} className="rounded-[1.75rem] border border-border bg-white p-6 shadow-sm">
              <div className="mb-4 inline-flex rounded-2xl bg-brand-600/10 p-3 text-brand-600"><Icon size={18} /></div>
              <p className="text-sm uppercase tracking-[0.18em] text-muted">{label}</p>
              <p className="mt-2 text-3xl font-semibold text-ink">{status === 'generating' ? '--' : formatNumber(value)}</p>
            </div>
          ))}
        </motion.div>

        {(plan?.rental_recommendations || []).length > 0 && (
          <div className="rounded-[1.75rem] border border-amber-300 bg-amber-50 p-5">
            <div className="mb-4 flex items-center gap-2 text-amber-800">
              <AlertTriangle size={17} />
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em]">AI rental options · approval required</h2>
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              {plan.rental_recommendations.map((recommendation) => (
                <div key={recommendation.id} className="rounded-2xl border border-amber-200 bg-white p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">{recommendation.profile}</p>
                  <h3 className="mt-2 text-lg font-semibold text-ink">{recommendation.vehicle_type}</h3>
                  <p className="mt-2 text-sm text-muted">
                    Up to {recommendation.capacity_positions} pallets · {formatNumber(recommendation.capacity_kg)} kg · licence {recommendation.required_permit}
                  </p>
                  <p className="mt-3 text-xl font-bold text-ink">≈ €{formatNumber(recommendation.estimated_cost_eur)}</p>
                  <button
                    type="button"
                    disabled={status !== 'ready' || isVerified}
                    onClick={() => approveRental(recommendation)}
                    className="mt-4 w-full rounded-xl bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    Approve and regenerate
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Unassigned deliveries are now shown as a draggable tray inside the
            Truck timeline (GanttBoard) so they can be dropped straight onto a
            truck lane. */}

        {/* ── Verify / Lock ── centered above the Gantt board ── */}
        {plan && (
          <div className="flex flex-col items-center gap-2 py-1">
            {!isVerified ? (
              <button
                type="button"
                onClick={() => setIsVerified(true)}
                className="inline-flex items-center gap-2.5 rounded-full bg-emerald-600 px-8 py-3 text-sm font-semibold text-white shadow-md transition hover:bg-emerald-700 hover:shadow-lg"
              >
                <ShieldCheck size={18} />
                Verify &amp; Lock Plan
              </button>
            ) : (
              <div className="flex flex-wrap items-center justify-center gap-3">
                <div className="inline-flex items-center gap-2.5 rounded-full bg-emerald-100 px-5 py-2.5 text-sm font-semibold text-emerald-700 ring-2 ring-emerald-300">
                  <ShieldCheck size={16} />
                  Plan Verified &amp; Locked
                </div>
                <button
                  type="button"
                  onClick={() => setIsVerified(false)}
                  className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-4 py-2.5 text-sm font-medium text-[#6b6b7b] transition hover:bg-[#faf8f5]"
                >
                  <ShieldOff size={14} />
                  Unlock Plan
                </button>
              </div>
            )}
            {isVerified && (
              <p className="text-xs text-[#6b6b7b]">Any modifications to this plan require a written justification.</p>
            )}
          </div>
        )}

        {status === 'generating' && !plan ? (
          <div className="rounded-[2rem] border border-border bg-white p-8 shadow-sm">
            <div className="h-96 rounded-2xl bg-[#f0eee9] animate-pulse" />
          </div>
        ) : (
          // min-w-0 lets GanttBoard's 1800px scroller shrink inside the column
          // and scroll horizontally instead of overflowing the page.
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

        {/* Single unified map: today's routes (real roads, per-truck filter,
            selection synced with the timeline) + the live control tower. */}
        {plan && (
          <ControlTowerPanel
            plan={plan}
            day={day}
            selectedTruckId={selectedTruckId}
            onSelectTruck={setSelectedTruckId}
          />
        )}

        {plan && (
          <DisruptionPanel
            plan={plan}
            day={day}
            onApplyPlan={(next) => setPlan(withManualMarkers(withResourceLanes(next, resourceFleet)))}
          />
        )}

        {plan && (
          <ConfidencePanel plan={plan} day={day} objective={plan.objective} />
        )}

        {plan && <ExplainPanel plan={plan} />}

        {plan && (
          <StressTestPanel day={day} activeTrucks={activeTrucks} objective={plan.objective} />
        )}

        {plan && (
          <>
            <PlanTable
              plan={plan}
              exporting={exporting}
              onExport={plan?.source_file ? handleExport : null}
            />

            {isVerified && <PlanChangeLog entries={changeLog} />}
          </>
        )}
      </motion.div>

      <AddDeliveryModal
        open={modalOpen}
        trucks={plan?.trucks || []}
        onClose={() => setModalOpen(false)}
        onAdd={addDelivery}
      />

      {pendingAction && (
        <JustificationModal
          action={pendingAction.description}
          onConfirm={confirmPendingAction}
          onCancel={() => setPendingAction(null)}
        />
      )}
    </div>
  );
}
