"use client";

import { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Truck, CheckCircle, AlertCircle, Wrench, Navigation, Link2, Link2Off } from 'lucide-react';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';
import { drivers as initialDrivers, trucks as initialTrucks } from '../../data/coficabData';
import { useDrivers, useFleet } from '../../hooks/useFleet';
import { updateTruckStatus } from '../services/api';
import {
  applyTruckStatusOverrides,
  applyDriverStatusOverrides,
  applyTruckAssignmentOverrides,
  canSyncTruckStatus,
  normalizeDriverStatus,
  normalizeTruckStatus,
  TRUCK_STATUS_OPTIONS,
  TRUCK_STATUS_STYLES,
  TRUCK_STATUS_TO_API,
  writeDriverStatusOverride,
  writeTruckAssignmentOverride,
  writeTruckStatusOverride,
} from '../../utils/truckStatus';

const statusOptions = ['Active', 'En pause', 'En route'];
const shiftOptions = ['Jour', 'Nuit'];

// A driver is only assignable when not paused; a truck only when not out of service.
const PAUSED_DRIVER_STATUS = 'En pause';
const UNAVAILABLE_TRUCK_DISPLAY = new Set(['Broken down', 'Maintenance']);

const DRIVER_STATUS_STYLES = {
  Active: 'bg-[#ecfdf5] text-[#15803d]',
  'En route': 'bg-[#eff6ff] text-[#2563eb]',
  'En pause': 'bg-[#fef3c7] text-[#b45309]',
};

const isTruckAvailable = (truck) => !UNAVAILABLE_TRUCK_DISPLAY.has(truck?.status);
const isDriverAssignable = (driver) => driver?.status !== PAUSED_DRIVER_STATUS;

function normalizeTruck(truck) {
  return {
    id: truck.id,
    plate_number: truck.plate_number,
    type: truck.type,
    capacity: truck.capacity ?? truck.capacite_kg ?? 0,
    max_pallets: truck.max_pallets ?? truck.max_palettes ?? 0,
    assigned_driver: truck.assigned_driver ?? truck.chauffeur_defaut_id ?? null,
    status: normalizeTruckStatus(truck.status),
  };
}

function normalizeDriver(driver) {
  const status = normalizeDriverStatus(driver.status);
  return {
    id: driver.id,
    full_name: driver.full_name,
    phone: driver.phone,
    status,
    shift: driver.shift || 'Jour',
    assigned_truck: driver.assigned_truck ?? driver.camion_defaut_id ?? null,
  };
}

// Reconcile the two sides into ONE source of truth: the truck's `assigned_driver`.
// Links are merged from both directions (truck.chauffeur_defaut_id AND
// driver.camion_defaut_id) so the seed can never leave the tables disagreeing.
function reconcilePairing(trucks, drivers) {
  const link = {}; // truckId -> driverId
  trucks.forEach((t) => { if (t.assigned_driver != null) link[String(t.id)] = t.assigned_driver; });
  drivers.forEach((d) => {
    if (d.assigned_truck != null && link[String(d.assigned_truck)] == null) link[String(d.assigned_truck)] = d.id;
  });
  return trucks.map((t) => ({ ...t, assigned_driver: link[String(t.id)] ?? null }));
}

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

export default function RessourcesPage() {
  const { trucks: apiTrucks, mutate: mutateFleet } = useFleet();
  const { drivers: apiDrivers } = useDrivers();
  const [chatMessages, setChatMessages] = useState([
    'La page Ressources est prête. Gérez l’affectation chauffeurs / camions et les statuts en un seul endroit.',
  ]);
  const [drivers, setDrivers] = useState(() => applyDriverStatusOverrides(initialDrivers.map(normalizeDriver)));
  const [trucks, setTrucks] = useState(() =>
    applyTruckAssignmentOverrides(
      applyTruckStatusOverrides(reconcilePairing(initialTrucks.map(normalizeTruck), applyDriverStatusOverrides(initialDrivers.map(normalizeDriver))))
    )
  );
  const seededRef = useRef(false);

  // Seed ONCE, only after BOTH lists have loaded, so we never lock in a
  // half-loaded pairing. The truck holds the link; the driver side is derived.
  useEffect(() => {
    if (seededRef.current) return;
    if (!apiTrucks.length || !apiDrivers.length) return;
    const baseDrivers = applyDriverStatusOverrides(apiDrivers.map(normalizeDriver));
    setDrivers(baseDrivers);
    setTrucks(applyTruckAssignmentOverrides(applyTruckStatusOverrides(reconcilePairing(apiTrucks.map(normalizeTruck), baseDrivers))));
    seededRef.current = true;
  }, [apiTrucks, apiDrivers]);

  // Derived links (truck is authority): driverId -> truck, and lookups.
  const driverTruck = useMemo(() => {
    const map = {};
    trucks.forEach((truck) => { if (truck.assigned_driver != null) map[String(truck.assigned_driver)] = truck; });
    return map;
  }, [trucks]);
  const driverById = useMemo(() => Object.fromEntries(drivers.map((d) => [String(d.id), d])), [drivers]);

  const driverSummary = useMemo(
    () => ({
      total: drivers.length,
      active: drivers.filter((driver) => driver.status === 'Active').length,
      assigned: Object.keys(driverTruck).length,
    }),
    [drivers, driverTruck]
  );

  const truckSummary = useMemo(
    () => ({
      total: trucks.length,
      available: trucks.filter((truck) => truck.status === 'Available').length,
      brokenDown: trucks.filter((truck) => truck.status === 'Broken down').length,
      maintenance: trucks.filter((truck) => truck.status === 'Maintenance').length,
      inTransit: trucks.filter((truck) => truck.status === 'In transit').length,
      assigned: trucks.filter((truck) => truck.assigned_driver != null).length,
    }),
    [trucks]
  );

  const handleDriverStatusChange = (driverId, status) => {
    const nextStatus = normalizeDriverStatus(status);
    writeDriverStatusOverride(driverId, nextStatus);
    setDrivers((prev) => prev.map((driver) => (driver.id === driverId ? { ...driver, status: nextStatus } : driver)));
    // Dependency: a paused driver can't hold a truck — release it on both sides.
    if (nextStatus === PAUSED_DRIVER_STATUS) {
      setTrucks((prev) => prev.map((truck) => {
        if (String(truck.assigned_driver) !== String(driverId)) return truck;
        writeTruckAssignmentOverride(truck.id, null);
        return { ...truck, assigned_driver: null };
      }));
    }
    const name = driverById[String(driverId)]?.full_name || driverId;
    setChatMessages((prev) => [`${name} → statut : ${status}.`, ...prev.slice(0, 4)]);
  };

  const handleDriverShiftChange = (driverId, shift) => {
    setDrivers((prev) => prev.map((driver) => (driver.id === driverId ? { ...driver, shift } : driver)));
    const name = driverById[String(driverId)]?.full_name || driverId;
    setChatMessages((prev) => [`${name} → shift : ${shift}.`, ...prev.slice(0, 4)]);
  };

  const handleTruckStatusChange = async (truckId, status) => {
    const nextStatus = normalizeTruckStatus(status);
    const becomesUnavailable = UNAVAILABLE_TRUCK_DISPLAY.has(nextStatus);
    const releasedDriver = becomesUnavailable
      ? driverById[String(trucks.find((t) => String(t.id) === String(truckId))?.assigned_driver)]
      : null;

    writeTruckStatusOverride(truckId, nextStatus);
    setTrucks((prev) => prev.map((truck) => (
      String(truck.id) === String(truckId)
        // Dependency: an out-of-service truck can't keep its driver.
        ? { ...truck, status: nextStatus, assigned_driver: becomesUnavailable ? null : truck.assigned_driver }
        : truck
    )));
    if (becomesUnavailable) writeTruckAssignmentOverride(truckId, null);

    const truckLabel = `Camion ${truckId}`;
    setChatMessages((prev) => [
      releasedDriver
        ? `${truckLabel} → ${nextStatus}. ${releasedDriver.full_name} libéré automatiquement.`
        : `${truckLabel} → ${nextStatus}.`,
      ...prev.slice(0, 4),
    ]);

    if (!canSyncTruckStatus(truckId)) return;
    try {
      await updateTruckStatus(truckId, TRUCK_STATUS_TO_API[nextStatus] || nextStatus);
      mutateFleet?.();
    } catch {
      setChatMessages((prev) => [`${truckLabel} mis à jour localement ; synchro base indisponible.`, ...prev.slice(0, 4)]);
    }
  };

  // Single assignment handler — the truck holds the link, the driver side is
  // derived, so the two tables can never disagree. Handles assign and unassign
  // from either table. Re-pairing a driver/truck frees their previous partner.
  const handleAssignment = (truckId, driverId) => {
    const tId = truckId ? String(truckId) : null;
    const dId = driverId ? String(driverId) : null;

    // Guard against illegal links (unavailable truck / paused driver).
    if (tId && !isTruckAvailable(trucks.find((t) => String(t.id) === tId))) return;
    if (dId && !isDriverAssignable(driverById[dId])) return;

    setTrucks((prev) => {
      let next = prev.map((truck) => ({ ...truck }));
      if (dId) next = next.map((t) => (String(t.assigned_driver) === dId ? { ...t, assigned_driver: null } : t));
      if (tId) next = next.map((t) => (String(t.id) === tId ? { ...t, assigned_driver: dId } : t));
      next.forEach((truck) => writeTruckAssignmentOverride(truck.id, truck.assigned_driver));
      return next;
    });

    const name = dId ? (driverById[dId]?.full_name || dId) : null;
    setChatMessages((prev) => [
      dId && tId ? `${name} ↔ Camion ${tId} liés.` : dId ? `${name} libéré.` : `Camion ${tId} libéré.`,
      ...prev.slice(0, 4),
    ]);
  };

  const availableDrivers = drivers.filter((driver) => isDriverAssignable(driver) && !driverTruck[String(driver.id)]);
  const availableTrucks = trucks.filter((truck) => truck.status === 'Available' && truck.assigned_driver == null);

  return (
    <div className="p-8 min-h-screen bg-[#eef2f7]">
      <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
        <motion.div
          variants={item}
          className="rounded-[2rem] border border-transparent bg-gradient-to-r from-[#faf5ff] via-[#eef6ff] to-[#effbf7] p-8 shadow-[0_24px_80px_-50px_rgba(15,23,42,0.2)]"
        >
          <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.3em] text-brand-600">Resource Operations</p>
              <h1 className="mt-3 text-4xl font-bold text-[#111827]">Good morning, Ghada</h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-[#4b5563]">A premium control center for your fleet, drivers, and daily assignments. Everything is designed for faster decisions and clearer resource visibility.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <div className="rounded-[1.75rem] border border-[#e5e7eb] bg-white px-6 py-5 shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.32em] text-[#6b7280]">Drivers libres</p>
                <p className="mt-3 text-3xl font-semibold text-[#111827]">{availableDrivers.length}</p>
                <p className="mt-2 text-xs text-[#6b7280]">Prêts à être assignés</p>
              </div>
              <div className="rounded-[1.75rem] border border-[#e5e7eb] bg-white px-6 py-5 shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.32em] text-[#6b7280]">Camions libres</p>
                <p className="mt-3 text-3xl font-semibold text-[#111827]">{availableTrucks.length}</p>
                <p className="mt-2 text-xs text-[#6b7280]">Disponibles pour la tournée</p>
              </div>
              <div className="rounded-[1.75rem] border border-[#e5e7eb] bg-white px-6 py-5 shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.32em] text-[#6b7280]">Assignments</p>
                <p className="mt-3 text-3xl font-semibold text-[#111827]">{truckSummary.assigned}</p>
                <p className="mt-2 text-xs text-[#6b7280]">Camions actuellement attachés</p>
              </div>
            </div>
          </div>
        </motion.div>

        <motion.div variants={container} className="grid gap-6 xl:grid-cols-4">
          <motion.div
            variants={item}
            whileHover={{ y: -3, boxShadow: '0 4px 20px rgba(15,23,42,0.12)' }}
            className="rounded-[1.75rem] bg-white p-6 border border-[#e5e7eb] shadow-sm"
          >
            <p className="text-sm uppercase tracking-[0.18em] text-[#6b7280]">Available</p>
            <p className="mt-4 text-4xl font-semibold text-[#111827]">{truckSummary.available}</p>
            <p className="mt-3 text-sm text-[#6b7280]">Camions prêts pour départ immédiat.</p>
          </motion.div>

          <motion.div
            variants={item}
            whileHover={{ y: -3, boxShadow: '0 4px 20px rgba(15,23,42,0.12)' }}
            className="rounded-[1.75rem] bg-white p-6 border border-[#e5e7eb] shadow-sm"
          >
            <p className="text-sm uppercase tracking-[0.18em] text-[#6b7280]">Broken down</p>
            <p className="mt-4 text-4xl font-semibold text-[#111827]">{truckSummary.brokenDown}</p>
            <p className="mt-3 text-sm text-[#6b7280]">Camions nécessitant une intervention.</p>
          </motion.div>

          <motion.div
            variants={item}
            whileHover={{ y: -3, boxShadow: '0 4px 20px rgba(15,23,42,0.12)' }}
            className="rounded-[1.75rem] bg-white p-6 border border-[#e5e7eb] shadow-sm"
          >
            <p className="text-sm uppercase tracking-[0.18em] text-[#6b7280]">Maintenance</p>
            <p className="mt-4 text-4xl font-semibold text-[#111827]">{truckSummary.maintenance}</p>
            <p className="mt-3 text-sm text-[#6b7280]">Entretien et vérifications en cours.</p>
          </motion.div>

          <motion.div
            variants={item}
            whileHover={{ y: -3, boxShadow: '0 4px 20px rgba(15,23,42,0.12)' }}
            className="rounded-[1.75rem] bg-white p-6 border border-[#e5e7eb] shadow-sm"
          >
            <p className="text-sm uppercase tracking-[0.18em] text-[#6b7280]">In transit</p>
            <p className="mt-4 text-4xl font-semibold text-[#111827]">{truckSummary.inTransit}</p>
            <p className="mt-3 text-sm text-[#6b7280]">Camions actifs sur la route.</p>
          </motion.div>
        </motion.div>

      {/* Section principale avec tables */}
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="space-y-6"
        >
          {/* Driver Management */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="rounded-[2rem] bg-white p-6 border border-[#e5e7eb] shadow-sm transition hover:shadow-lg"
          >
            <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-[#6b7280]">Driver management</p>
                <h2 className="text-2xl font-semibold text-[#111827]">Chauffeurs et statuts</h2>
                <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-muted">
                  <Link2 size={12} /> Affecter un chauffeur remplit le camion correspondant. Mettre un chauffeur en pause libère son camion.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-[#eef2ff] px-3 py-1 text-sm font-semibold text-[#4338ca]">{drivers.length} chauffeurs</span>
                <span className="rounded-full bg-[#f0fdf4] px-3 py-1 text-sm font-semibold text-[#15803d]">{driverSummary.active} actifs</span>
                <span className="rounded-full bg-[#f8fafc] px-3 py-1 text-sm font-semibold text-[#0f172a]">{driverSummary.assigned} assignés</span>
              </div>
            </div>
            <div className="overflow-hidden rounded-[1.5rem] border border-[#e5e7eb]">
              <div className="grid grid-cols-[1.2fr_1fr_1fr_1fr_1fr] gap-4 bg-[#eef4ff] px-6 py-4 text-sm font-semibold uppercase tracking-[0.15em] text-[#4b5563]">
                <span>Nom</span>
                <span>Statut</span>
                <span>Shift</span>
                <span>Camion</span>
                <span>Affectation</span>
              </div>
              <div className="divide-y divide-border bg-white max-h-96 overflow-y-auto">
                {drivers.map((driver) => (
                  <motion.div
                    key={driver.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="grid grid-cols-[1.2fr_1fr_1fr_1fr_1fr] gap-4 px-6 py-4 items-center text-sm text-ink hover:bg-canvas transition"
                  >
                    <div>
                      <p className="font-semibold">{driver.full_name}</p>
                      <p className="text-muted text-xs">{driver.phone}</p>
                    </div>
                    <div>
                      <select
                        value={driver.status}
                        onChange={(event) => handleDriverStatusChange(driver.id, event.target.value)}
                        className={`w-full rounded-xl border border-border px-3 py-2 text-sm font-semibold outline-none focus:ring-2 focus:ring-brand-600 transition ${DRIVER_STATUS_STYLES[driver.status] || 'bg-white text-ink'}`}
                      >
                        {statusOptions.map((status) => (
                          <option key={status} value={status}>{status}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <select
                        value={driver.shift}
                        onChange={(event) => handleDriverShiftChange(driver.id, event.target.value)}
                        className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition"
                      >
                        {shiftOptions.map((shift) => (
                          <option key={shift} value={shift}>{shift}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      {driverTruck[String(driver.id)] ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#f0fdf4] px-2.5 py-1 text-xs font-semibold text-[#15803d]">
                          <Link2 size={12} />
                          {driverTruck[String(driver.id)].id} · {driverTruck[String(driver.id)].plate_number}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted">
                          <Link2Off size={12} /> Aucun
                        </span>
                      )}
                    </div>
                    <div>
                      <select
                        value={driverTruck[String(driver.id)]?.id ?? ''}
                        disabled={!isDriverAssignable(driver)}
                        title={!isDriverAssignable(driver) ? 'Chauffeur en pause — indisponible pour affectation' : undefined}
                        onChange={(event) => handleAssignment(event.target.value || null, driver.id)}
                        className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition disabled:cursor-not-allowed disabled:bg-[#f3f4f6] disabled:text-muted"
                      >
                        <option value="">Aucun</option>
                        {trucks.map((truck) => {
                          const takenByOther = truck.assigned_driver != null && String(truck.assigned_driver) !== String(driver.id);
                          const unavailable = !isTruckAvailable(truck);
                          return (
                            <option key={truck.id} value={truck.id} disabled={takenByOther || unavailable}>
                              {truck.id} ({truck.plate_number})
                              {unavailable ? ` — ${truck.status}` : takenByOther ? ` — occupé (${driverById[String(truck.assigned_driver)]?.full_name || truck.assigned_driver})` : ''}
                            </option>
                          );
                        })}
                      </select>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>

          {/* Truck Management */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.25 }}
            className="rounded-[2rem] bg-white p-6 border border-[#e5e7eb] shadow-sm transition hover:shadow-lg"
          >
            <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-[#6b7280]">Truck management</p>
                <h2 className="text-2xl font-semibold text-[#111827]">Camions</h2>
                <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-muted">
                  <Link2 size={12} /> Affecter un chauffeur met à jour les deux tables. Un camion en panne / maintenance libère son chauffeur.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-[#fef3c7] px-3 py-1 text-sm font-semibold text-[#b45309]">{truckSummary.brokenDown} broken down</span>
                <span className="rounded-full bg-[#eff6ff] px-3 py-1 text-sm font-semibold text-[#1d4ed8]">{truckSummary.inTransit} in transit</span>
                <span className="rounded-full bg-[#f0fdf4] px-3 py-1 text-sm font-semibold text-[#15803d]">{truckSummary.available} available</span>
              </div>
            </div>
            <div className="overflow-hidden rounded-[1.5rem] border border-[#e5e7eb]">
              <div className="grid grid-cols-[1.2fr_1fr_0.9fr_1fr_1fr] gap-4 bg-[#eef4ff] px-6 py-4 text-sm font-semibold uppercase tracking-[0.15em] text-[#4b5563]">
                <span>Camion</span>
                <span>Type</span>
                <span>Capacité</span>
                <span>Statut</span>
                <span>Chauffeur</span>
              </div>
              <div className="divide-y divide-border bg-white max-h-96 overflow-y-auto">
                {trucks.map((truck) => (
                  <motion.div
                    key={truck.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="grid grid-cols-[1.2fr_1fr_0.9fr_1fr_1fr] gap-4 px-6 py-4 items-center text-sm text-ink hover:bg-canvas transition"
                  >
                    <div>
                      <p className="font-semibold">{truck.id}</p>
                      <p className="text-muted text-xs">{truck.plate_number}</p>
                    </div>
                    <div className="text-muted">{truck.type}</div>
                    <div>
                      <span className="inline-block bg-[#f0fdf4] text-[#22c55e] rounded-xl px-3 py-1 text-xs font-semibold">
                        {truck.capacity} kg
                      </span>
                    </div>
                    <div>
                      <select
                        value={truck.status}
                        onChange={(event) => handleTruckStatusChange(truck.id, event.target.value)}
                        className={`w-full rounded-xl border border-border px-3 py-2 text-sm font-semibold outline-none focus:ring-2 focus:ring-brand-600 ${TRUCK_STATUS_STYLES[truck.status] || 'bg-white text-ink'}`}
                      >
                        {TRUCK_STATUS_OPTIONS.map((status) => (
                          <option key={status} value={status}>{status}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <select
                        value={truck.assigned_driver || ''}
                        disabled={!isTruckAvailable(truck)}
                        title={!isTruckAvailable(truck) ? `Camion ${truck.status.toLowerCase()} — aucun chauffeur ne peut être affecté` : undefined}
                        onChange={(event) => handleAssignment(truck.id, event.target.value || null)}
                        className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition disabled:cursor-not-allowed disabled:bg-[#f3f4f6] disabled:text-muted"
                      >
                        <option value="">Aucun</option>
                        {drivers.map((driver) => {
                          const truckOfDriver = driverTruck[String(driver.id)];
                          const takenByOther = truckOfDriver && String(truckOfDriver.id) !== String(truck.id);
                          const paused = !isDriverAssignable(driver);
                          return (
                            <option key={driver.id} value={driver.id} disabled={takenByOther || paused}>
                              {driver.full_name}
                              {paused ? ' — en pause' : takenByOther ? ` — occupé (Camion ${truckOfDriver.id})` : ''}
                            </option>
                          );
                        })}
                      </select>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Activity Feed - Sidebar */}
        <motion.aside
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="space-y-6"
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.35 }}
            className="rounded-[2rem] bg-white p-6 border border-[#e5e7eb] shadow-sm transition hover:shadow-lg h-full"
          >
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-[#6b7280]">Ressources feed</p>
                <h2 className="text-xl font-semibold text-[#111827]">Activité</h2>
              </div>
              <span className="rounded-full bg-[#eef2ff] px-3 py-1 text-sm font-semibold text-[#4338ca]">Live</span>
            </div>
            <ChatPanel
              messages={chatMessages}
              title="Resources Optiroute"
              context={{ page: 'resources', driverSummary, truckSummary, drivers, trucks }}
            />
          </motion.div>
        </motion.aside>
      </div>
    </motion.div>
  </div>
  );
}
