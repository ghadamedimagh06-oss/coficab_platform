"use client";

import { useEffect, useState } from 'react';
import { getKpi, getLiveTracking } from '../services/api';
import StatCard from '../../components/cards/StatCard';
import BarChart from '../../components/charts/BarChart';
import ChatPanel from '../../components/chat/ChatPanel';

export default function DashboardPage() {
  const [metrics, setMetrics] = useState({ planning_time: 0, detection_latency: 0, data_error_rate: 0 });
  const [tracking, setTracking] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);

  useEffect(() => {
    async function load() {
      try {
        const kpi = await getKpi();
        setMetrics(kpi);
        const live = await getLiveTracking();
        const items = live?.tracking_data ? Object.values(live.tracking_data) : live || [];
        setTracking(items);
        setChatMessages((prev) => [
          'Welcome back! Live logistics data is up-to-date and ready for review.',
          ...prev,
        ]);
      } catch (error) {
        setChatMessages((prev) => ['Unable to load real-time data. Please verify backend connectivity.', ...prev]);
      }
    }
    load();
  }, []);

  const kpiCards = [
    {
      title: 'Planning time',
      value: `${metrics.planning_time ?? 0}s`, 
      hint: 'Automated planning latency',
      icon: '⏱️',
    },
    {
      title: 'Detection latency',
      value: `${metrics.detection_latency ?? 0}s`,
      hint: 'Delay and anomaly detection',
      icon: '⚡',
    },
    {
      title: 'Error rate',
      value: `${((metrics.data_error_rate ?? 0) * 100).toFixed(2)}%`, 
      hint: 'Quality of ingested data',
      icon: '📊',
    },
  ];

  const chartData = [
    { label: 'Planning', value: metrics.planning_time ?? 0 },
    { label: 'Detection', value: metrics.detection_latency ?? 0 },
    { label: 'Errors', value: (metrics.data_error_rate ?? 0) * 100 },
  ];

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1.8fr)_minmax(0,1fr)]">
      <section className="space-y-8">
        <div className="grid gap-6 sm:grid-cols-3">
          {kpiCards.map((card) => (
            <StatCard key={card.title} title={card.title} value={card.value} hint={card.hint} icon={card.icon} />
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
          <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
            <div className="flex items-center justify-between mb-6">
              <div>
                <p className="text-sm text-slate-400">Operational snapshot</p>
                <h2 className="text-2xl font-semibold">Executive overview</h2>
              </div>
              <span className="rounded-full bg-slate-800 px-3 py-2 text-sm text-slate-200">Real-time</span>
            </div>
            <BarChart title="Performance distribution" data={chartData} labelKey="label" valueKey="value" />
          </div>

          <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
            <h2 className="text-xl font-semibold mb-4">Live fleet highlights</h2>
            <div className="space-y-4">
              {tracking.slice(0, 5).map((truck, index) => (
                <div key={truck.transport_id || index} className="rounded-3xl border border-slate-800 bg-slate-950/80 p-4">
                  <p className="font-semibold">{truck.transport_id || `Vehicle ${index + 1}`}</p>
                  <p className="text-sm text-slate-400">Status: {truck.status || 'On time'}</p>
                  <p className="text-sm text-slate-400">ETA: {truck.eta_hours ? `${truck.eta_hours.toFixed(1)}h` : 'Unknown'}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400">Audit readiness</p>
              <h2 className="text-lg font-semibold">Change tracking is active</h2>
            </div>
            <span className="rounded-full bg-emerald-500/15 px-3 py-2 text-sm text-emerald-200">Live</span>
          </div>
          <div className="space-y-3 text-sm text-slate-400">
            <p>All dashboard operations are timestamped and traceable.</p>
            <p>AI planning events are captured for audit review.</p>
          </div>
        </div>

        <ChatPanel messages={chatMessages} />
      </aside>
    </div>
  );
}
