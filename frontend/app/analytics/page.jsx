"use client";

import { useEffect, useState } from 'react';
import { getKpi, getTransports } from '../services/api';
import ChatPanel from '../../components/chat/ChatPanel';
import BarChart from '../../components/charts/BarChart';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';

export default function AnalyticsPage() {
  const [metrics, setMetrics] = useState({ planning_time: 0, detection_latency: 0, data_error_rate: 0 });
  const [transports, setTransports] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);

  useEffect(() => {
    async function loadData() {
      try {
        const kpi = await getKpi();
        setMetrics(kpi);
        const transportData = await getTransports();
        setTransports(Array.isArray(transportData) ? transportData : []);
        setChatMessages((prev) => [
          'Analytics loaded. Comparison metrics are ready for review.',
          ...prev,
        ]);
      } catch (error) {
        setChatMessages((prev) => ['Unable to load analytics. Verify backend availability.', ...prev]);
      }
    }
    loadData();
  }, []);

  const truckScores = transports.slice(0, 5).map((item, index) => ({
    label: item.vehicle || `Truck ${index + 1}`,
    value: item.distance_km ? Math.min(100, item.distance_km / 10) : 15,
  }));

  const driverScores = transports.slice(0, 5).map((item, index) => ({
    label: item.driver || `Driver ${index + 1}`,
    value: item.distance_km ? Math.min(100, item.distance_km / 11) : 20,
  }));

  return (
    <div className="grid gap-8 xl:grid-cols-[1.5fr_0.85fr]">
      <section className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-3">
          <StatCard title="Forecast gain" value="+7.4%" hint="Improvement from last run" icon={<IconBubble kind="chart" />} />
          <StatCard title="Error rate" value={`${((metrics.data_error_rate ?? 0) * 100).toFixed(2)}%`} hint="Data integrity" icon={<IconBubble kind="default" />} />
          <StatCard title="Latency" value={`${metrics.detection_latency ?? 0}s`} hint="Detection speed" icon={<IconBubble kind="bolt" />} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <BarChart title="Truck performance" data={truckScores} />
          <BarChart title="Driver efficiency" data={driverScores} />
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <h2 className="text-xl font-semibold">KPI trends</h2>
          <p className="mt-3 text-sm text-slate-400">Use this page to compare operational performance, risk, and cost impact. The analytics module is designed to highlight where AI planning improved outcomes.</p>
        </div>

        <ChatPanel messages={chatMessages} />
      </aside>
    </div>
  );
}
