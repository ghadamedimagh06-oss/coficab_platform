"use client";

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { getLiveTracking } from '../services/api';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';

const TruckMap = dynamic(() => import('../../components/map/TruckMap'), { ssr: false });

export default function MapPage() {
  const [tracking, setTracking] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);

  useEffect(() => {
    async function loadTracking() {
      try {
        const live = await getLiveTracking();
        const items = live?.tracking_data ? Object.values(live.tracking_data) : live || [];
        setTracking(items);
        setChatMessages((prev) => [
          'Real-time truck positions refreshed. Click a marker for ETA and status details.',
          ...prev,
        ]);
      } catch (error) {
        setChatMessages((prev) => ['Unable to refresh map data. Check backend polling settings.', ...prev]);
      }
    }
    loadTracking();
  }, []);

  const statusCounts = tracking.reduce(
    (acc, item) => {
      const status = item.status?.toLowerCase();
      if (status?.includes('critical')) acc.critical += 1;
      else if (status?.includes('delay')) acc.warning += 1;
      else acc.onTime += 1;
      return acc;
    },
    { onTime: 0, warning: 0, critical: 0 }
  );

  return (
    <div className="grid gap-8 xl:grid-cols-[1.5fr_0.9fr]">
      <section className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-3">
          <StatCard title="Total trucks" value={tracking.length} hint="Active vehicles in the fleet" icon="🚚" />
          <StatCard title="On time" value={statusCounts.onTime} hint="Healthy routes" icon="✅" />
          <StatCard title="Critical delays" value={statusCounts.critical} hint="Requires intervention" icon="🚨" />
        </div>

        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <TruckMap trucks={tracking} />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-5">
            <p className="text-sm text-slate-400">Route stability</p>
            <p className="mt-3 text-3xl font-semibold text-brand">{tracking.length ? ((statusCounts.onTime / tracking.length) * 100).toFixed(0) : 0}%</p>
          </div>
          <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-5">
            <p className="text-sm text-slate-400">Delay risk</p>
            <p className="mt-3 text-3xl font-semibold text-orange-400">{statusCounts.warning}</p>
          </div>
          <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-5">
            <p className="text-sm text-slate-400">Critical alerts</p>
            <p className="mt-3 text-3xl font-semibold text-red-500">{statusCounts.critical}</p>
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <h2 className="text-xl font-semibold">Map insights</h2>
          <p className="mt-3 text-sm text-slate-400">The live map reflects current vehicle positions, ETA, and route status. Polling refresh keeps the view aligned with backend tracking data.</p>
        </div>

        <ChatPanel messages={chatMessages} />
      </aside>
    </div>
  );
}
