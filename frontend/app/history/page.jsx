"use client";

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart3,
  CalendarDays,
  CalendarRange,
  RefreshCcw,
} from 'lucide-react';
import { deliveryHistory2026, deliveryHistory2026Meta } from '../../data/deliveryHistory2026';

const VIEWS = [
  { id: 'daily', label: 'Daily', icon: CalendarDays },
  { id: 'weekly', label: 'Weekly', icon: CalendarRange },
  { id: 'monthly', label: 'Monthly', icon: BarChart3 },
];

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
};

function dateFromIso(value) {
  return value ? new Date(`${value}T00:00:00`) : null;
}

function formatDate(value) {
  const date = dateFromIso(value);
  if (!date || Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function startOfWeek(date) {
  const next = new Date(date);
  const day = (next.getDay() + 6) % 7;
  next.setDate(next.getDate() - day);
  return next;
}

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function periodFor(row, view) {
  const date = dateFromIso(row.delivery_date);
  if (!date || Number.isNaN(date.getTime())) {
    return { key: 'unknown', label: 'Unknown date' };
  }
  if (view === 'weekly') {
    const start = startOfWeek(date);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return {
      key: isoDate(start),
      label: `${formatDate(isoDate(start))} - ${formatDate(isoDate(end))}`,
    };
  }
  if (view === 'monthly') {
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    return {
      key,
      label: date.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }),
    };
  }
  return { key: row.delivery_date, label: formatDate(row.delivery_date) };
}

function pct(value) {
  if (value == null || Number.isNaN(Number(value))) return '-';
  return `${Math.round(Number(value) * 100)}%`;
}

function number(value, digits = 0) {
  if (value == null || Number.isNaN(Number(value))) return '-';
  return Number(value).toLocaleString('en-US', { maximumFractionDigits: digits });
}

export default function DailyPlanningPage() {
  // Data is baked straight from the 2026 delivery workbook
  // (docs/history data/Planning de Livraison 2026 v0.xlsx → "Details local delivery").
  const meta = deliveryHistory2026Meta;
  const [rows, setRows] = useState(deliveryHistory2026);
  const [view, setView] = useState('daily');
  const [period, setPeriod] = useState('');
  const [loading, setLoading] = useState(false);

  function loadHistory() {
    setLoading(true);
    setRows(deliveryHistory2026);
    // Purely cosmetic spinner — the workbook data is already in the bundle.
    setTimeout(() => setLoading(false), 250);
  }

  const periods = useMemo(() => {
    const map = new Map();
    rows.forEach((row) => {
      const next = periodFor(row, view);
      if (!map.has(next.key)) {
        map.set(next.key, { ...next, count: 0 });
      }
      map.get(next.key).count += 1;
    });
    return [...map.values()].sort((a, b) => String(b.key).localeCompare(String(a.key)));
  }, [rows, view]);

  useEffect(() => {
    setPeriod((current) => (periods.some((p) => p.key === current) ? current : periods[0]?.key || ''));
  }, [periods]);

  const visibleRows = useMemo(() => (
    rows.filter((row) => periodFor(row, view).key === period)
  ), [rows, view, period]);

  const causeStats = useMemo(() => {
    const counts = new Map();
    rows.filter((row) => row.is_late).forEach((row) => {
      const cause = row.delay_cause || 'Cause non renseignée';
      counts.set(cause, (counts.get(cause) || 0) + 1);
    });
    return [...counts.entries()]
      .map(([cause, count]) => ({ cause, count }))
      .sort((a, b) => b.count - a.count);
  }, [rows]);

  const selectedPeriod = periods.find((p) => p.key === period);
  const maxCause = Math.max(1, ...causeStats.map((cause) => cause.count));

  return (
    <div className="min-h-screen bg-canvas p-8">
      <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
        <motion.header variants={item} className="rounded-[2rem] border border-border bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-brand-600">Delivery History</p>
              <h1 className="mt-3 text-4xl font-bold text-ink">Historique des livraisons</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
                Execution history from the 2026 delivery workbook, with daily, weekly, and monthly views.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-2xl border border-border bg-canvas px-4 py-3 text-sm text-muted">
                <span className="font-semibold text-ink">{meta?.file_name || 'Planning de Livraison 2026 v0.xlsx'}</span>
              </div>
              <button
                type="button"
                onClick={loadHistory}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-2xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-50"
              >
                <RefreshCcw size={16} className={loading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          </div>
        </motion.header>

        <motion.section variants={item} className="rounded-[2rem] border border-border bg-white shadow-sm">
          <div className="flex flex-col gap-5 border-b border-border p-6 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted">View</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink">{selectedPeriod?.label || 'No period selected'}</h2>
            </div>
            <div className="flex flex-wrap gap-3">
              {VIEWS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setView(id)}
                  className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold transition ${
                    view === id
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'border border-border bg-white text-ink hover:bg-canvas'
                  }`}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="border-b border-border px-6 py-5">
            <div className="flex gap-3 overflow-x-auto pb-1">
              {periods.map((next) => (
                <button
                  key={next.key}
                  type="button"
                  onClick={() => setPeriod(next.key)}
                  className={`shrink-0 rounded-2xl px-4 py-2 text-sm font-semibold transition ${
                    period === next.key
                      ? 'bg-ink text-white'
                      : 'border border-border bg-canvas text-ink hover:bg-white'
                  }`}
                >
                  {next.label}
                  <span className="ml-2 text-xs opacity-70">{next.count}</span>
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="p-10 text-center text-sm text-muted">Loading delivery history...</div>
          ) : visibleRows.length === 0 ? (
            <div className="p-10 text-center text-sm text-muted">No delivery history found for this period.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-[1280px] w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-canvas">
                    {[
                      'Date',
                      'N Voyage',
                      'Client',
                      'Matricule',
                      'Chauffeur',
                      'Position',
                      'Weight',
                      'ETD planned',
                      'ETD real',
                      'ETA target',
                      'ETA real',
                      'OTD',
                      'Cause retard',
                    ].map((heading) => (
                      <th key={heading} className="px-4 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {visibleRows.slice(0, 350).map((row) => (
                    <tr key={row.id} className="transition hover:bg-canvas">
                      <td className="whitespace-nowrap px-4 py-3 font-medium text-ink">{formatDate(row.delivery_date)}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink">{row.voyage || '-'}</td>
                      <td className="max-w-[280px] px-4 py-3">
                        <span className="block truncate font-semibold text-ink" title={row.client || '-'}>
                          {row.client || '-'}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-ink">{row.truck || '-'}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-ink">{row.driver || '-'}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right font-semibold text-ink">{number(row.positions)}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right text-ink">{number(row.weight, 1)}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink">{row.planned_etd || '-'}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink">{row.real_etd || '-'}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink">{row.target_eta_customer || '-'}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink">{row.real_eta_customer || '-'}</td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                          row.is_late ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {row.new_otd != null ? pct(row.new_otd) : pct(row.otd)}
                        </span>
                      </td>
                      <td className="max-w-[240px] px-4 py-3">
                        <span className="block truncate text-ink" title={row.delay_cause || ''}>
                          {row.delay_cause || '-'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visibleRows.length > 350 ? (
                <div className="border-t border-border px-6 py-4 text-xs text-muted">
                  Showing first 350 rows from {visibleRows.length} deliveries in this period.
                </div>
              ) : null}
            </div>
          )}
        </motion.section>

        <motion.section variants={item} className="rounded-[2rem] border border-border bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted">Retard de livraison</p>
              <h2 className="mt-2 text-2xl font-semibold text-ink">Cause statistics</h2>
            </div>
            <p className="text-sm text-muted">{causeStats.length} causes across the workbook</p>
          </div>

          {causeStats.length === 0 ? (
            <div className="mt-6 rounded-2xl bg-canvas px-5 py-6 text-sm text-muted">
              No delivery delay causes recorded for this period.
            </div>
          ) : (
            <div className="mt-6 grid gap-3 lg:grid-cols-2">
              {causeStats.map((cause) => (
                <div key={cause.cause} className="rounded-2xl border border-border bg-canvas px-4 py-3">
                  <div className="flex items-center justify-between gap-4">
                    <span className="truncate text-sm font-semibold text-ink" title={cause.cause}>{cause.cause}</span>
                    <span className="text-sm font-semibold text-rose-700">{cause.count}</span>
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-white">
                    <div
                      className="h-2 rounded-full bg-rose-500"
                      style={{ width: `${Math.max(6, (cause.count / maxCause) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </motion.section>
      </motion.div>
    </div>
  );
}
