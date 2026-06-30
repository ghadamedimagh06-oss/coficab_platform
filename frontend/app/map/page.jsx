"use client";

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { CalendarDays, RefreshCcw, Route } from 'lucide-react';
import { generateDailyPlan, getLiveTracking } from '../services/api';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';
import { palette } from '@/lib/theme';

// Leaflet touches `window` at import time, so load the map client-side only.
const RouteMap = dynamic(() => import('../../components/planning/RouteMap'), { ssr: false });

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

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
  const [liveTracking, setLiveTracking] = useState({ tracking_data: [], source: 'TFM_SCRAPER' });
  const [tfmStatus, setTfmStatus] = useState('');

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
    refreshTfmScrape();
  }, []);

  async function refreshTfmScrape() {
    setTfmStatus('refreshing');
    try {
      const live = await getLiveTracking();
      const rows = Array.isArray(live?.tracking_data) ? live.tracking_data : [];
      setLiveTracking(live || { tracking_data: [], source: 'TFM_SCRAPER' });
      setTfmStatus('ready');
      setMessages((prev) => [
        `TFM scraper refreshed: ${rows.length} transport samples from ${live?.source || 'TFM_SCRAPER'}.`,
        ...prev,
      ]);
    } catch {
      setTfmStatus('error');
    }
  }

  const stats = useMemo(() => {
    const trucksUsed = (plan?.trucks || []).filter((t) => (t.trips || []).length > 0).length;
    const tfmRows = Array.isArray(liveTracking?.tracking_data) ? liveTracking.tracking_data : [];
    const delayed = tfmRows.filter((row) => Number(row.delay_minutes || 0) > 10 || row.status === 'delayed').length;
    return { trucksUsed, clients: countStops(plan), unassigned: plan?.unassigned?.length || 0, tfmRows: tfmRows.length, delayed };
  }, [plan, liveTracking]);

  return (
    <div className="p-8 min-h-screen bg-canvas">
      <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
        <motion.div variants={item} className="rounded-[2rem] border border-border bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-brand-600">Live Map</p>
              <h1 className="mt-3 text-4xl font-bold text-ink">Today’s clients &amp; truck routes</h1>
              <p className="mt-2 text-sm leading-6 text-muted">Every delivery for the day plotted across Tunisia, with each truck’s road from the COFICAB Sidi Hassine depot.</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="inline-flex items-center gap-2 rounded-2xl border border-border bg-white px-4 py-2 text-sm font-semibold text-ink">
                <CalendarDays size={16} className="text-brand-600" />
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
                className="inline-flex items-center gap-2 rounded-2xl border border-border bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-canvas disabled:opacity-60"
              >
                <RefreshCcw size={16} className={status === 'loading' ? 'animate-spin' : ''} />
                Refresh
              </button>
              <Link
                href="/generated-daily-planning"
                className="inline-flex items-center gap-2 rounded-2xl bg-brand-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-brand-700 shadow-sm"
              >
                <Route size={16} />
                Open planning
              </Link>
            </div>
          </div>
        </motion.div>

        <motion.div variants={container} className="grid gap-6 xl:grid-cols-[1.5fr_0.9fr]">
          <section className="space-y-6">
            <motion.div variants={item} className="grid gap-6 sm:grid-cols-5">
              <StatCard title="Trucks routed" value={status === 'loading' ? '—' : stats.trucksUsed} hint="Vehicles on the road today" icon={<IconBubble kind="truck" />} />
              <StatCard title="Clients" value={status === 'loading' ? '—' : stats.clients} hint="Delivery stops planned" icon={<IconBubble kind="chart" />} />
              <StatCard title="Unassigned" value={status === 'loading' ? '—' : stats.unassigned} hint="Need dispatcher review" icon={<IconBubble kind="bolt" />} />
              <StatCard title="TFM samples" value={stats.tfmRows} hint="Scraped from TFM website" icon={<IconBubble kind="spark" />} />
              <StatCard title="TFM delays" value={stats.delayed} hint="Detected by scraper" icon={<IconBubble kind="bolt" />} />
            </motion.div>

            <motion.div variants={item}>
              {status === 'loading' && !plan ? (
                <div className="rounded-[2rem] border border-border bg-white p-5 shadow-sm">
                  <div className="h-[560px] rounded-[1.5rem] bg-[#f0eee9] animate-pulse" />
                </div>
              ) : (
                <RouteMap plan={plan} selectedTruckId={selectedTruckId} onSelectTruck={setSelectedTruckId} height={560} />
              )}
            </motion.div>
          </section>

          <motion.aside variants={item} className="space-y-6">
            <div className="rounded-[2rem] border border-border bg-white p-6 shadow-sm">
              <p className="text-sm text-muted">Reference</p>
              <h2 className="text-2xl font-semibold text-ink">Map legend</h2>
              <ul className="mt-4 space-y-3 text-sm text-muted">
                <li className="flex items-center gap-3"><span className="h-3 w-3 rounded-full" style={{ background: '#facc15' }} /> COFICAB Sidi Hassine depot</li>
                <li className="flex items-center gap-3"><span className="h-3 w-3 rounded-full" style={{ background: palette.brand[600] }} /> Client stop (coloured by truck)</li>
                <li className="flex items-center gap-3"><span className="h-3 w-3 rounded-full" style={{ background: '#9ca3af' }} /> Unassigned client</li>
              </ul>
              <p className="mt-4 text-xs leading-5 text-[#9e9aa4]">Click a truck chip or its route to trace that vehicle’s ordered stops. Routes follow the real road network via OSRM.</p>
            </div>

            <div className="rounded-[2rem] border border-cyan-300 bg-cyan-50 p-6 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">TFM website scraper</p>
              <p className="mt-2 text-sm text-cyan-950">
                Hardcoded scraper mode: transport rows are treated as if Agent 4 extracted them from the TFM portal screen.
              </p>
              <div className="mt-4 rounded-2xl bg-white/80 p-4 text-sm text-cyan-950">
                <div className="flex items-center justify-between gap-3">
                  <span>Source</span>
                  <span className="font-semibold">{liveTracking?.source || 'TFM_SCRAPER'}</span>
                </div>
                <div className="mt-2 flex items-center justify-between gap-3">
                  <span>Portal</span>
                  <span className="text-right text-xs font-semibold">tfm.coficab.local</span>
                </div>
              </div>
              <button
                type="button"
                disabled={tfmStatus === 'refreshing'}
                onClick={refreshTfmScrape}
                className="mt-4 w-full rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              >
                {tfmStatus === 'refreshing' ? 'Refreshing scraper...' : 'Refresh TFM scrape'}
              </button>
              {tfmStatus && tfmStatus !== 'refreshing' && <p className="mt-2 text-xs text-cyan-800">Status: {tfmStatus}</p>}
              <div className="mt-4 space-y-2">
                {(liveTracking?.tracking_data || []).slice(0, 3).map((row) => (
                  <div key={row.transport_id} className="rounded-xl bg-white px-3 py-2 text-xs text-cyan-950">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-semibold">{row.transport_id}</span>
                      <span>{row.status}</span>
                    </div>
                    <div className="mt-1 text-cyan-800">{Number(row.delay_minutes || 0)} min delay</div>
                  </div>
                ))}
              </div>
            </div>

            <ChatPanel
              messages={messages}
              title="Map Optiroute"
              context={{ page: 'map', day, status, selectedTruckId, plan }}
            />
          </motion.aside>
        </motion.div>
      </motion.div>
    </div>
  );
}
