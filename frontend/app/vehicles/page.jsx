"use client";

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Truck, CheckCircle, BarChart3 } from 'lucide-react';
import { trucks as initialTrucks } from '../../data/coficabData';

const statsAnimation = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

const statusOptions = ['Disponible', 'En route', 'En panne', 'En maintenance'];

const statusStyles = {
  Disponible: 'bg-[#ecfdf5] text-[#15803d]',
  'En route': 'bg-[#eff6ff] text-[#2563eb]',
  'En panne': 'bg-[#fee2e2] text-[#dc2626]',
  'En maintenance': 'bg-[#fef3c7] text-[#b45309]',
};

export default function VehiclesPage() {
  const [trucks, setTrucks] = useState(initialTrucks);

  const handleStatusChange = (truckId, status) => {
    setTrucks((prev) => prev.map((truck) => (truck.id === truckId ? { ...truck, status } : truck)));
  };

  const summary = useMemo(
    () => ({
      total: trucks.length,
      active: trucks.filter((truck) => truck.status === 'En route').length,
      available: trucks.filter((truck) => truck.status === 'Disponible').length,
    }),
    [trucks]
  );
  const sortedTrucks = useMemo(
    () => [...trucks].sort((a, b) => b.capacity - a.capacity),
    [trucks]
  );
  return (
    <div className="p-8 min-h-screen bg-[#f8f7f3]">
      <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[2rem] border border-[#e8e5df] bg-white p-8 shadow-sm mb-8">
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Fleet vehicles</p>
        <h1 className="mt-3 text-4xl font-bold text-[#1a1a2e]">Vehicle fleet overview</h1>
        <p className="mt-2 text-sm text-[#6b6b7b] max-w-2xl">Track truck availability, status, and operational readiness in one control center.</p>
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
        <div className="flex items-center justify-between bg-[#f8f7f3] px-6 py-5 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b5563]">
          <span>Vehicle details</span>
          <span className="rounded-full bg-[#eff6ff] px-3 py-1 text-[11px] font-semibold text-[#2563eb]">{summary.total} trucks</span>
        </div>
        <div className="divide-y divide-[#e8e5df] bg-white">
          {sortedTrucks.map((truck) => (
            <div key={truck.id} className="grid grid-cols-[1.5fr_1fr_1fr_1fr] gap-4 px-6 py-4 text-sm text-[#1a1a2e] items-center hover:bg-[#faf8f5] transition">
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
                  className={`w-full rounded-xl border border-[#e8e5df] px-3 py-2 text-sm font-semibold ${statusStyles[truck.status] || 'bg-white text-[#1a1a2e]'}`}
                >
                  {statusOptions.map((status) => (
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
