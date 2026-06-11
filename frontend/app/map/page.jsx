"use client";

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { CalendarDays, RefreshCcw } from 'lucide-react';
import { generateDailyPlan } from '../services/api';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';

// Leaflet touches `window` at import time, so load the map client-side only.
const RouteMap = dynamic(() => import('../../components/planning/RouteMap'), { ssr: false });

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function countStops(plan) {
  return (plan?.trucks || []).reduce(
    (sum, t) => sum + (t.trips || []).reduce((n, trip) => n + (trip.stops || []).length, 0),
    0,
  );
}

export default function MapPage() {
  const [day, setDay] = useState('');
  const [plan, setPlan] = useState(null);
  const [status, setStatus] = useState('loading');
  const [selectedTruckId, setSelectedTruckId] = useState(null);
  const [messages, setMessages] = useState([]);

  async function load(nextDay) {
    setStatus('loading');
    try {
      const next = await generateDailyPlan(nextDay);
      setPlan(next);
      setSelectedTruckId(null);
      setStatus('ready');
      setMessages((prev) => [`Loaded ${countStops(next)} client stops for ${nextDay}. Click a truck to trace its road.`, ...prev]);
    } catch (err) {
      setStatus('ready');
      setMessages((prev) => [`Unable to load the plan for ${nextDay}: ${err?.response?.data?.detail || err.message}`, ...prev]);
    }
  }

  useEffect(() => {
    const initial = todayIso();
    setDay(initial);
    load(initial);
  }, []);

  const stats = useMemo(() => {
    const trucksUsed = (plan?.trucks || []).filter((t) => (t.trips || []).length > 0).length;
    return { trucksUsed, clients: countStops(plan), unassigned: plan?.unassigned?.length || 0 };
  }, [plan]);

  return (
    <div className="min-h-screen bg-[#f8f7f3] p-8">
      <div className="mb-8 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Live Map</p>
          <h1 className="mt-3 text-3xl font-semibold text-[#1a1a2e]">Today’s clients &amp; truck routes</h1>
          <p className="mt-2 text-sm text-[#6b6b7b]">Every delivery for the day plotted across Tunisia, with each truck’s road from the depot.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-4 py-2 text-sm font-semibold text-[#1a1a2e]">
            <CalendarDays size={16} />
            <input
              type="date"
              value={day}
              onChange={(e) => { setDay(e.target.value); load(e.target.value); }}
              className="bg-transparent outline-none"
            />
          </label>
          <button
            type="button"
            onClick={() => load(day)}
            disabled={status === 'loading'}
            className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-5 py-2 text-sm font-semibold text-[#1a1a2e] transition hover:bg-[#faf8f5] disabled:opacity-60"
          >
            <RefreshCcw size={16} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid gap-8 xl:grid-cols-[1.5fr_0.9fr]">
        <section className="space-y-6">
          <div className="grid gap-6 sm:grid-cols-3">
            <StatCard title="Trucks routed" value={status === 'loading' ? '—' : stats.trucksUsed} hint="Vehicles on the road today" icon={<IconBubble kind="truck" />} />
            <StatCard title="Clients" value={status === 'loading' ? '—' : stats.clients} hint="Delivery stops planned" icon={<IconBubble kind="chart" />} />
            <StatCard title="Unassigned" value={status === 'loading' ? '—' : stats.unassigned} hint="Need dispatcher review" icon={<IconBubble kind="bolt" />} />
          </div>

          {status === 'loading' && !plan ? (
            <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <div className="h-[520px] rounded-[1.25rem] bg-[#f0eee9] animate-pulse" />
            </div>
          ) : (
            <RouteMap plan={plan} selectedTruckId={selectedTruckId} onSelectTruck={setSelectedTruckId} height={560} />
          )}
        </section>

        <aside className="space-y-6">
          <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-[#1a1a2e]">Map legend</h2>
            <ul className="mt-3 space-y-2 text-sm text-[#6b6b7b]">
              <li className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ background: '#facc15' }} /> COFICAB Mégrine depot</li>
              <li className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ background: '#7c3aed' }} /> Client stop (coloured by truck)</li>
              <li className="flex items-center gap-2"><span className="h-3 w-3 rounded-full" style={{ background: '#9ca3af' }} /> Unassigned client</li>
            </ul>
            <p className="mt-3 text-xs text-[#9e9aa4]">Click a truck chip or its route to trace that vehicle’s ordered stops. Routes are straight legs (road routing via OSRM is planned).</p>
          </div>

          <ChatPanel messages={messages} />
        </aside>
      </div>
    </div>
  );
}
