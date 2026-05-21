"use client";

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Users, Clock3, CheckCircle } from 'lucide-react';
import { drivers } from '../../data/coficabData';

const statsAnimation = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

export default function DriversPage() {
  const summary = useMemo(
    () => ({
      total: drivers.length,
      active: drivers.filter((driver) => driver.status === 'Active').length,
      nightShift: drivers.filter((driver) => driver.shift === 'Nuit').length,
    }),
    []
  );

  return (
    <div className="p-8 min-h-screen bg-[#f8f7f3]">
      <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[2rem] border border-[#e8e5df] bg-white p-8 shadow-sm mb-8">
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Driver operations</p>
        <h1 className="mt-3 text-4xl font-bold text-[#1a1a2e]">Driver roster overview</h1>
        <p className="mt-2 text-sm text-[#6b6b7b] max-w-2xl">Monitor driver availability, shift coverage, and the team ready for dispatch.</p>
      </motion.div>

      <div className="grid gap-6 xl:grid-cols-3 mb-8">
        <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="rounded-2xl bg-[#eef2ff] p-3 text-[#4338ca]"><Users size={20} /></span>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Drivers</p>
            </div>
          </div>
          <p className="text-4xl font-semibold text-[#111827]">{summary.total}</p>
          <p className="mt-2 text-sm text-[#6b7280]">Total drivers currently in the fleet.</p>
        </motion.div>

        <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="rounded-2xl bg-[#ecfdf5] p-3 text-[#15803d]"><CheckCircle size={20} /></span>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Active</p>
            </div>
          </div>
          <p className="text-4xl font-semibold text-[#111827]">{summary.active}</p>
          <p className="mt-2 text-sm text-[#6b7280]">Drivers available for assignment.</p>
        </motion.div>

        <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-3 mb-4">
            <span className="rounded-2xl bg-[#f0f9ff] p-3 text-[#0f172a]"><Clock3 size={20} /></span>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Night shift</p>
            </div>
          </div>
          <p className="text-4xl font-semibold text-[#111827]">{summary.nightShift}</p>
          <p className="mt-2 text-sm text-[#6b7280]">Drivers scheduled for nights.</p>
        </motion.div>
      </div>

      <motion.div variants={statsAnimation} initial="hidden" animate="show" className="rounded-[2rem] bg-white border border-[#e8e5df] shadow-sm overflow-hidden">
        <div className="bg-[#f8f7f3] px-6 py-5 text-sm font-semibold uppercase tracking-[0.18em] text-[#4b5563]">Driver roster</div>
        <div className="divide-y divide-[#e8e5df] bg-white">
          {drivers.map((driver) => (
            <div key={driver.id} className="grid grid-cols-[1.8fr_1fr_1fr_1fr] gap-4 px-6 py-4 items-center text-sm text-[#1a1a2e] hover:bg-[#faf8f5] transition">
              <div>
                <p className="font-semibold">{driver.full_name}</p>
                <p className="text-[#6b7280] text-xs">{driver.phone}</p>
              </div>
              <div className="text-[#111827] font-semibold">{driver.shift}</div>
              <div className="text-[#6b7280]">{driver.assigned_truck || 'Aucun'}</div>
              <div className={`rounded-full px-3 py-1 text-xs font-semibold ${driver.status === 'Active' ? 'bg-[#ecfdf5] text-[#15803d]' : 'bg-[#fef3c7] text-[#b45309]'}`}>
                {driver.status}
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
