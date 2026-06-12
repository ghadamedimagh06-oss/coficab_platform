"use client";

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Truck, CheckCircle, BarChart3 } from 'lucide-react';
import { trucks as initialTrucks } from '../../data/coficabData';
import { useFleet } from '../../hooks/useFleet';
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

const statsAnimation = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function normalizeTruck(truck) {
  return {
    id: truck.id,
    plate_number: truck.plate_number,
    type: truck.type,
    capacity: truck.capacity ?? truck.capacite_kg ?? 0,
    max_pallets: truck.max_pallets ?? truck.max_palettes ?? 0,
    status: normalizeTruckStatus(truck.status),
  };
}

export default function VehiclesPage() {
  const { trucks: apiTrucks, mutate } = useFleet();
  const [trucks, setTrucks] = useState(() => applyTruckStatusOverrides(initialTrucks.map(normalizeTruck)));

  useEffect(() => {
    if (apiTrucks.length) {
      setTrucks(applyTruckStatusOverrides(apiTrucks.map(normalizeTruck)));
    }
  }, [apiTrucks]);

  const handleStatusChange = async (truckId, status) => {
    const nextStatus = normalizeTruckStatus(status);
    writeTruckStatusOverride(truckId, nextStatus);
    setTrucks((prev) => prev.map((truck) => (String(truck.id) === String(truckId) ? { ...truck, status: nextStatus } : truck)));

    if (!canSyncTruckStatus(truckId)) {
      return;
    }

    try {
      await updateTruckStatus(truckId, TRUCK_STATUS_TO_API[nextStatus] || nextStatus);
      mutate?.();
    } catch {
      // Manual status still stays visible when the database/API is offline.
    }
  };

  const summary = useMemo(
    () => ({
      total: trucks.length,
      active: trucks.filter((truck) => truck.status === 'In transit').length,
      available: trucks.filter((truck) => truck.status === 'Available').length,
    }),
    [trucks]
  );
  const sortedTrucks = useMemo(
    () => [...trucks].sort((a, b) => b.capacity - a.capacity),
    [trucks]
  );
  return (
    <div className="p-8 min-h-screen bg-canvas">
      <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[2rem] border border-border bg-white p-8 shadow-sm mb-8">
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-brand-600">Fleet vehicles</p>
        <h1 className="mt-3 text-4xl font-bold text-ink">Vehicle fleet overview</h1>
        <p className="mt-2 text-sm text-muted max-w-2xl">Track truck availability, status, and operational readiness in one control center.</p>
      </motion.div>

      <div className="grid gap-6 xl:grid-cols-3 mb-8">
        <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="rounded-2xl bg-[#eef2ff] p-3 text-[#4338ca]"><Truck size={20} /></span>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Total trucks</p>
            </div>
          </div>
          <p className="text-4xl font-semibold text-[#111827]">{summary.total}</p>
          <p className="mt-2 text-sm text-[#6b7280]">Complete fleet size currently loaded.</p>
        </motion.div>

        <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="rounded-2xl bg-[#ecfdf5] p-3 text-[#15803d]"><CheckCircle size={20} /></span>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Available</p>
            </div>
          </div>
          <p className="text-4xl font-semibold text-[#111827]">{summary.available}</p>
          <p className="mt-2 text-sm text-[#6b7280]">Ready for assignment and dispatch.</p>
        </motion.div>

        <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="rounded-2xl bg-[#f0f9ff] p-3 text-[#0f172a]"><BarChart3 size={20} /></span>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">In transit</p>
            </div>
          </div>
          <p className="text-4xl font-semibold text-[#111827]">{summary.active}</p>
          <p className="mt-2 text-sm text-[#6b7280]">Vehicles currently on the road.</p>
        </motion.div>
      </div>

      <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[2rem] bg-white border border-[#e8e5eb] shadow-sm overflow-hidden">
        <div className="flex items-center justify-between bg-canvas px-6 py-5 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b5563]">
          <span>Vehicle details</span>
          <span className="rounded-full bg-[#eff6ff] px-3 py-1 text-[11px] font-semibold text-[#2563eb]">{summary.total} trucks</span>
        </div>
        <div className="divide-y divide-border bg-white">
          {sortedTrucks.map((truck) => (
            <div key={truck.id} className="grid grid-cols-[1.5fr_1fr_1fr_1fr] gap-4 px-6 py-4 text-sm text-ink items-center hover:bg-canvas transition">
              <div>
                <p className="font-semibold">{truck.id}</p>
                <p className="text-[#6b7280] text-xs">{truck.plate_number}</p>
              </div>
              <div className="text-[#6b7280]">{truck.type}</div>
              <div className="text-[#111827] font-semibold">{truck.capacity} kg</div>
              <div>
                <select
                  value={truck.status}
                  onChange={(event) => handleStatusChange(truck.id, event.target.value)}
                  className={`w-full rounded-xl border border-border px-3 py-2 text-sm font-semibold ${TRUCK_STATUS_STYLES[truck.status] || 'bg-white text-ink'}`}
                >
                  {TRUCK_STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
