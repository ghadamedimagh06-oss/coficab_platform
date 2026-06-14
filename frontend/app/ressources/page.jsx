"use client";

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Truck, CheckCircle, AlertCircle, Wrench, Navigation } from 'lucide-react';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';
import { drivers as initialDrivers, trucks as initialTrucks } from '../../data/coficabData';
import { useDrivers, useFleet } from '../../hooks/useFleet';
import { updateTruckStatus } from '../services/api';
import {
  applyTruckStatusOverrides,
  canSyncTruckStatus,
  normalizeTruckStatus,
  TRUCK_STATUS_OPTIONS,
  TRUCK_STATUS_STYLES,
  TRUCK_STATUS_TO_API,
  writeTruckStatusOverride,
} from '../../utils/truckStatus';

const statusOptions = ['Active', 'En pause', 'En route'];
const shiftOptions = ['Jour', 'Nuit'];

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
  const status = driver.status === 'ACTIF' || driver.status === 'Active' ? 'Active' : 'En pause';
  return {
    id: driver.id,
    full_name: driver.full_name,
    phone: driver.phone,
    status,
    shift: driver.shift || 'Jour',
    assigned_truck: driver.assigned_truck ?? driver.camion_defaut_id ?? null,
  };
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
  const [drivers, setDrivers] = useState(initialDrivers.map(normalizeDriver));
  const [trucks, setTrucks] = useState(() => applyTruckStatusOverrides(initialTrucks.map(normalizeTruck)));

  useEffect(() => {
    if (apiTrucks.length) {
      setTrucks(applyTruckStatusOverrides(apiTrucks.map(normalizeTruck)));
    }
  }, [apiTrucks]);

  useEffect(() => {
    if (apiDrivers.length) {
      setDrivers(apiDrivers.map(normalizeDriver));
    }
  }, [apiDrivers]);

  const driverSummary = useMemo(
    () => ({
      total: drivers.length,
      active: drivers.filter((driver) => driver.status === 'Active').length,
      assigned: drivers.filter((driver) => driver.assigned_truck).length,
    }),
    [drivers]
  );

  const truckSummary = useMemo(
    () => ({
      total: trucks.length,
      available: trucks.filter((truck) => truck.status === 'Available').length,
      brokenDown: trucks.filter((truck) => truck.status === 'Broken down').length,
      maintenance: trucks.filter((truck) => truck.status === 'Maintenance').length,
      inTransit: trucks.filter((truck) => truck.status === 'In transit').length,
      assigned: trucks.filter((truck) => truck.assigned_driver).length,
    }),
    [trucks]
  );

  const handleDriverStatusChange = (driverId, status) => {
    setDrivers((prev) => prev.map((driver) => (driver.id === driverId ? { ...driver, status } : driver)));
    setChatMessages((prev) => [`Statut de ${driverId} mis à jour : ${status}.`, ...prev.slice(0, 4)]);
  };

  const handleDriverShiftChange = (driverId, shift) => {
    setDrivers((prev) => prev.map((driver) => (driver.id === driverId ? { ...driver, shift } : driver)));
    setChatMessages((prev) => [`Shift de ${driverId} mis à jour : ${shift}.`, ...prev.slice(0, 4)]);
  };

  const handleTruckStatusChange = async (truckId, status) => {
    const nextStatus = normalizeTruckStatus(status);
    writeTruckStatusOverride(truckId, nextStatus);
    setTrucks((prev) => prev.map((truck) => (String(truck.id) === String(truckId) ? { ...truck, status: nextStatus } : truck)));
    setChatMessages((prev) => [`Truck ${truckId} status updated: ${nextStatus}.`, ...prev.slice(0, 4)]);

    if (!canSyncTruckStatus(truckId)) {
      return;
    }

    try {
      await updateTruckStatus(truckId, TRUCK_STATUS_TO_API[nextStatus] || nextStatus);
      mutateFleet?.();
    } catch {
      setChatMessages((prev) => [`Truck ${truckId} was updated locally; database sync is unavailable.`, ...prev.slice(0, 4)]);
    }
  };

  const handleAssignment = (truckId, driverId) => {
    setTrucks((prevTrucks) =>
      prevTrucks.map((truck) => {
        if (String(truck.id) === String(truckId)) {
          return { ...truck, assigned_driver: driverId || null };
        }
        if (String(truck.assigned_driver) === String(driverId)) {
          return { ...truck, assigned_driver: null };
        }
        return truck;
      })
    );

    setDrivers((prevDrivers) =>
      prevDrivers.map((driver) => {
        if (String(driver.id) === String(driverId)) {
          return { ...driver, assigned_truck: truckId };
        }
        if (String(driver.assigned_truck) === String(truckId)) {
          return { ...driver, assigned_truck: null };
        }
        return driver;
      })
    );

    setChatMessages((prev) => [`${driverId ? `${driverId} affecté à ${truckId}` : `Affectation supprimée sur ${truckId}`}.`, ...prev.slice(0, 4)]);
  };

  const availableDrivers = drivers.filter((driver) => !driver.assigned_truck);
  const availableTrucks = trucks.filter((truck) => !truck.assigned_driver && truck.status === 'Available');

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
                        className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition"
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
                      <span className={`text-sm font-medium ${driver.assigned_truck ? 'text-[#22c55e]' : 'text-muted'}`}>
                        {driver.assigned_truck || 'Aucun'}
                      </span>
                    </div>
                    <div>
                      <select
                        value={driver.assigned_truck || ''}
                        onChange={(event) => handleAssignment(event.target.value || null, driver.id)}
                        className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition"
                      >
                        <option value="">Aucun</option>
                        {trucks.map((truck) => (
                          <option key={truck.id} value={truck.id}>{truck.id} ({truck.plate_number})</option>
                        ))}
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
                        onChange={(event) => handleAssignment(truck.id, event.target.value || null)}
                        className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition"
                      >
                        <option value="">Aucun</option>
                        {drivers.map((driver) => (
                          <option key={driver.id} value={driver.id}>{driver.full_name}</option>
                        ))}
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
