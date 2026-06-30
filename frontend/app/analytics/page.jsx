"use client";

import { useEffect, useState } from 'react';
import { getCarbonHistory, getTransports } from '../services/api';
import ChatPanel from '../../components/chat/ChatPanel';
import BarChart from '../../components/charts/BarChart';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';

const EMPTY_SUMMARY = {
  emissions_kg_co2e: 0,
  fuel_l: 0,
  distance_km: 0,
  tonne_km: 0,
  kg_co2e_per_km: null,
  kg_co2e_per_tonne_km: null,
};

export default function AnalyticsPage() {
  const [groupBy, setGroupBy] = useState('week');
  const [carbon, setCarbon] = useState({ summary: EMPTY_SUMMARY, history: [], factor: null });
  const [transports, setTransports] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [carbonData, transportData] = await Promise.all([
          getCarbonHistory(groupBy),
          getTransports(),
        ]);
        setCarbon(carbonData || { summary: EMPTY_SUMMARY, history: [], factor: null });
        setTransports(Array.isArray(transportData) ? transportData : []);
        setChatMessages((prev) => [
          `Carbon history loaded with ${groupBy} aggregation.`,
          ...prev,
        ]);
      } catch (error) {
        setChatMessages((prev) => ['Unable to load analytics. Verify backend availability.', ...prev]);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [groupBy]);

  const summary = carbon.summary || EMPTY_SUMMARY;
  const carbonBars = (carbon.history || []).slice(-12).map((row) => ({
    label: row.label,
    value: row.emissions_kg_co2e,
  }));
  const truckDistances = transports.slice(0, 5).map((item, index) => ({
    label: item.vehicle || `Truck ${index + 1}`,
    value: Number(item.distance_km || 0),
  }));

  return (
    <div className="grid gap-8 xl:grid-cols-[1.5fr_0.85fr]">
      <section className="space-y-6">
        <div className="flex flex-col gap-4 rounded-[2rem] border border-[#e8e5df] bg-white p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#15803d]">Environmental analytics</p>
            <h1 className="mt-2 text-3xl font-bold text-[#1a1a2e]">Estimated carbon history</h1>
            <p className="mt-2 text-sm text-[#6b6b7b]">Fuel-derived CO₂e estimate using the configured conversion factor.</p>
          </div>
          <div className="flex gap-2">
            {['day', 'week', 'month'].map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setGroupBy(option)}
                className={`rounded-xl px-4 py-2 text-sm font-semibold capitalize ${
                  groupBy === option ? 'bg-[#15803d] text-white' : 'bg-[#f1f5f0] text-[#4b5563]'
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-6 sm:grid-cols-3">
          <StatCard title="CO₂e emitted" value={`${summary.emissions_kg_co2e.toLocaleString()} kg`} hint="Selected reporting range" icon={<IconBubble kind="chart" />} />
          <StatCard title="Fuel consumed" value={`${summary.fuel_l.toLocaleString()} L`} hint={`${summary.distance_km.toLocaleString()} km travelled`} icon={<IconBubble kind="default" />} />
          <StatCard
            title="Carbon intensity"
            value={summary.kg_co2e_per_tonne_km == null ? '—' : `${summary.kg_co2e_per_tonne_km} kg/T.km`}
            hint={`${summary.tonne_km.toLocaleString()} tonne-km`}
            icon={<IconBubble kind="bolt" />}
          />
        </div>

        {loading ? (
          <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-8 text-sm text-[#6b6b7b]">Loading carbon history…</div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-2">
            <BarChart title="CO₂e history (kg)" data={carbonBars} />
            <BarChart title="Truck distance (km)" data={truckDistances} />
          </div>
        )}
      </section>

      <aside className="space-y-6">
        <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-[#1a1a2e]">Calculation method</h2>
          <p className="mt-3 text-sm text-[#6b6b7b]">CO₂e = consumed fuel × configured emission factor.</p>
          <p className="mt-4 text-2xl font-bold text-[#15803d]">
            {carbon.factor?.kg_co2e_per_l ?? '—'} kg CO₂e/L
          </p>
          <p className="mt-1 text-xs text-[#9ca3af]">{carbon.factor?.source || 'Factor source unavailable'}</p>
          <p className="mt-1 text-xs text-[#9ca3af]">Boundary: {carbon.factor?.boundary || 'unspecified'} · Effective: {carbon.factor?.effective_from || 'unversioned'}</p>
        </div>

        <ChatPanel
          messages={chatMessages}
          title="Analytics Optiroute"
          context={{ page: 'analytics', metrics: summary, transportCount: transports.length }}
        />
      </aside>
    </div>
  );
}
