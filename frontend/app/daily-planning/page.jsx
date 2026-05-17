"use client";

import { useCallback, useEffect, useState } from 'react';
import { getDailyPlanning } from '../services/api';
import StatCard from '../../components/cards/StatCard';

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const REFRESH_INTERVAL = 30;

const STATUS_CONFIG = {
  completed:  { label: 'Completed',  cls: 'bg-emerald-50 text-emerald-700 border border-emerald-200' },
  in_transit: { label: 'In transit', cls: 'bg-blue-50   text-blue-700   border border-blue-200'   },
  pending:    { label: 'Pending',    cls: 'bg-amber-50  text-amber-700  border border-amber-200'  },
};

const PRIORITY_CONFIG = {
  urgent: { label: 'Urgent', cls: 'bg-rose-50   text-rose-700   border border-rose-200'   },
  high:   { label: 'High',   cls: 'bg-orange-50 text-orange-700 border border-orange-200' },
  normal: { label: 'Normal', cls: 'bg-[#f0ede8] text-[#6b6b7b]'                          },
  low:    { label: 'Low',    cls: 'bg-slate-50  text-slate-500  border border-slate-200'  },
};

function formatDate(date) {
  return date.toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });
}

function formatTime(date) {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export default function DailyPlanningPage() {
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(new Date());
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL);

  const todayName = DAYS[now.getDay()];

  // Live clock — ticks every second
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDailyPlanning(DAYS[new Date().getDay()]);
      setDeliveries(Array.isArray(data) ? data : []);
    } catch {
      setError('Unable to load planning data. Showing last known state.');
    } finally {
      setLoading(false);
      setCountdown(REFRESH_INTERVAL);
    }
  }, []);

  // Initial load
  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh countdown — reuses the live clock tick
  useEffect(() => {
    const id = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { fetchData(); return REFRESH_INTERVAL; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [fetchData]);

  const stats = {
    total:      deliveries.length,
    completed:  deliveries.filter((d) => d.status === 'completed').length,
    in_transit: deliveries.filter((d) => d.status === 'in_transit').length,
    pending:    deliveries.filter((d) => d.status === 'pending').length,
  };

  return (
    <div className="space-y-8">

      {/* ── Header card ── */}
      <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-[#6b6b7b]">
              COFICAB — Weekly Planning
            </p>
            <h1 className="mt-1 text-3xl font-semibold text-[#1a1a2e]">Daily Planning</h1>
            <p className="mt-1 text-sm text-[#6b6b7b]">{formatDate(now)}</p>
          </div>

          <div className="flex flex-col items-start gap-3 xl:items-end">
            <div className="rounded-[1.5rem] bg-[#7c3aed] px-7 py-4 text-center min-w-[170px]">
              <p className="text-[10px] uppercase tracking-[0.28em] text-white/70">Current time</p>
              <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-white">
                {formatTime(now)}
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs text-[#6b6b7b]">
              <span
                className={`inline-block h-2 w-2 rounded-full transition-colors ${
                  loading ? 'bg-amber-400' : 'bg-emerald-400'
                }`}
              />
              {loading ? 'Refreshing…' : `Auto-refresh in ${countdown}s`}
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {error}
          </div>
        )}
      </div>

      {/* ── Stat cards ── */}
      <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Deliveries today"
          value={stats.total}
          hint={`${todayName}'s complete plan`}
          icon="📦"
        />
        <StatCard
          title="Completed"
          value={stats.completed}
          hint="Delivered successfully"
          icon="✅"
          tone="text-emerald-600"
        />
        <StatCard
          title="In transit"
          value={stats.in_transit}
          hint="Currently on route"
          icon="🚛"
          tone="text-blue-600"
        />
        <StatCard
          title="Pending"
          value={stats.pending}
          hint="Awaiting departure"
          icon="⏳"
          tone="text-amber-600"
        />
      </div>

      {/* ── Deliveries table ── */}
      <div className="rounded-[2rem] border border-[#e8e5df] bg-white shadow-sm overflow-hidden">

        {/* Table header */}
        <div className="flex items-center justify-between border-b border-[#e8e5df] px-6 py-5">
          <div>
            <p className="text-sm text-[#6b6b7b]">Weekly planning — filtered by current day</p>
            <h2 className="text-2xl font-semibold text-[#1a1a2e]">
              {todayName}&rsquo;s Deliveries
            </h2>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="rounded-2xl border border-[#e8e5df] bg-[#faf8f5] px-4 py-2 text-sm font-medium text-[#1a1a2e] transition hover:bg-[#f0ede8] disabled:opacity-50"
          >
            Refresh
          </button>
        </div>

        {/* Loading bar */}
        {loading && (
          <div className="h-1 w-full bg-[#f0ede8]">
            <div className="h-1 w-1/3 animate-pulse rounded-full bg-[#7c3aed]" />
          </div>
        )}

        {/* Empty state */}
        {!loading && deliveries.length === 0 && (
          <div className="py-24 text-center">
            <p className="text-5xl">📭</p>
            <p className="mt-4 text-lg font-medium text-[#1a1a2e]">
              No deliveries scheduled for {todayName}
            </p>
            <p className="mt-1 text-sm text-[#6b6b7b]">
              Check the weekly planning file or ingest new data from the Admin panel.
            </p>
          </div>
        )}

        {/* Table */}
        {deliveries.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#e8e5df] bg-[#faf8f5]">
                  {['#', 'Client', 'Driver', 'Vehicle', 'Route', 'ETD', 'ETA', 'Dist (km)', 'Qty', 'Status', 'Priority'].map(
                    (col) => (
                      <th
                        key={col}
                        className="px-5 py-4 text-left text-[11px] font-medium uppercase tracking-[0.18em] text-[#6b6b7b] whitespace-nowrap"
                      >
                        {col}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e8e5df]">
                {deliveries.map((d, i) => {
                  const s = STATUS_CONFIG[d.status]   ?? STATUS_CONFIG.pending;
                  const p = PRIORITY_CONFIG[d.priority] ?? PRIORITY_CONFIG.normal;
                  return (
                    <tr key={d.id ?? i} className="transition hover:bg-[#faf8f5]">
                      <td className="px-5 py-4 text-[#9e9eaa]">{d.row_number ?? i + 1}</td>

                      <td className="px-5 py-4 max-w-[200px]">
                        <span className="block truncate font-medium text-[#1a1a2e]" title={d.client || d.end_location}>
                          {d.client || d.end_location || '—'}
                        </span>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap text-[#1a1a2e]">{d.driver}</td>

                      <td className="px-5 py-4 whitespace-nowrap font-mono text-xs text-[#1a1a2e]">
                        {d.vehicle}
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap">
                        <span className="text-[#1a1a2e]">{d.start_location}</span>
                        <span className="mx-2 text-[#9e9eaa]">→</span>
                        <span className="text-[#1a1a2e]">{d.end_location}</span>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap font-mono text-xs text-[#1a1a2e]">
                        {d.etd ?? '—'}
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap font-mono text-xs text-[#1a1a2e]">
                        {d.eta ?? '—'}
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap text-right text-[#1a1a2e]">
                        {d.distance_km != null ? d.distance_km.toFixed(1) : '—'}
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap text-right text-[#1a1a2e]">
                        {d.quantity ?? '—'}
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap">
                        <span className={`rounded-full px-3 py-1 text-xs font-medium ${s.cls}`}>
                          {s.label}
                        </span>
                      </td>

                      <td className="px-5 py-4 whitespace-nowrap">
                        <span className={`rounded-full px-3 py-1 text-xs font-medium ${p.cls}`}>
                          {p.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Footer row */}
        {deliveries.length > 0 && (
          <div className="border-t border-[#e8e5df] px-6 py-4 text-xs text-[#9e9eaa]">
            {deliveries.length} deliveries shown &middot; Data from&nbsp;
            <span className="font-medium text-[#6b6b7b]">weekly planning/</span> folder &middot; auto-refreshes every {REFRESH_INTERVAL}s
          </div>
        )}
      </div>
    </div>
  );
}
