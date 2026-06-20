"use client";

import { useState } from 'react';
import { Leaf, Fuel, Route, TreePine, Car, Gauge, Download, Loader2, Sparkles, FileText } from 'lucide-react';
import { getDailyPareto, getEsgReport } from '../../app/services/api';
import { openExecutiveReport } from './executiveReport';

const OBJECTIVES = [
  { key: 'green', label: 'Greenest', help: 'Fewest, fullest trucks — minimise CO₂', tone: 'emerald' },
  { key: 'balanced', label: 'Balanced', help: 'Default trade-off', tone: 'sky' },
  { key: 'fast', label: 'Fastest', help: 'Max parallelism — finish the day earliest', tone: 'violet' },
];

const TONE = {
  emerald: 'bg-emerald-500 text-emerald-50',
  sky: 'bg-sky-500 text-sky-50',
  violet: 'bg-violet-500 text-violet-50',
};

function num(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Carbon & ESG panel for a generated daily plan.
 *
 * - Headline cards: CO₂ emitted/saved vs the unconsolidated manual baseline,
 *   fuel, distance saved, and intuitive equivalences (trees, car-km).
 * - "Compare objectives" runs the Pareto frontier (green/balanced/fast) and lets
 *   the dispatcher apply any operating point to the live plan.
 * - "Export ESG report" downloads a structured sustainability report.
 */
export default function SustainabilityPanel({ plan, day, activeTrucks, onApplyPlan }) {
  const [pareto, setPareto] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [error, setError] = useState(null);

  const s = plan?.sustainability;
  if (!s) return null;

  const currentObjective = plan.objective || s.objective || 'balanced';

  async function runCompare() {
    setLoading(true);
    setError(null);
    try {
      const res = await getDailyPareto(day, ['green', 'balanced', 'fast'], activeTrucks);
      setPareto(res);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Comparison failed.');
    } finally {
      setLoading(false);
    }
  }

  async function exportReport() {
    setExporting(true);
    setError(null);
    try {
      const report = await getEsgReport(day, currentObjective);
      downloadJson(`COFICAB_ESG_report_${day}_${currentObjective}.json`, report);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Export failed.');
    } finally {
      setExporting(false);
    }
  }

  async function boardReport() {
    setReporting(true);
    setError(null);
    try {
      // Pull the structured ESG payload for completeness, then open a polished,
      // printable one-page report (browser "Save as PDF").
      const esg = await getEsgReport(day, currentObjective).catch(() => null);
      openExecutiveReport({ plan, day, esg });
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Report failed.');
    } finally {
      setReporting(false);
    }
  }

  function applyObjective(obj) {
    const next = pareto?.plans?.[obj];
    if (next && onApplyPlan) onApplyPlan(next);
  }

  const maxCo2 = pareto ? Math.max(...pareto.points.map((p) => p.co2_kg || 0), 1) : 1;

  return (
    <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-100 text-emerald-600">
            <Leaf size={18} />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-ink">Carbon &amp; ESG</h2>
            <p className="text-xs text-muted">
              vs. unconsolidated manual baseline · objective:{' '}
              <span className="font-medium capitalize">{currentObjective}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={runCompare}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm font-medium text-ink transition hover:bg-emerald-50 disabled:opacity-60"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            Compare objectives
          </button>
          <button
            type="button"
            onClick={boardReport}
            disabled={reporting}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
          >
            {reporting ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
            Board report (PDF)
          </button>
          <button
            type="button"
            onClick={exportReport}
            disabled={exporting}
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm font-medium text-ink transition hover:bg-emerald-50 disabled:opacity-60"
          >
            {exporting ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
            ESG JSON
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : null}

      {/* Headline metrics */}
      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric
          icon={<Leaf size={16} />}
          tone="text-emerald-600"
          label="CO₂ saved"
          value={`${num(s.co2_saved_kg)} kg`}
          hint={`${num(s.co2_saved_pct, 1)}% vs baseline`}
        />
        <Metric
          icon={<Gauge size={16} />}
          tone="text-ink"
          label="CO₂ emitted"
          value={`${num(s.co2_kg)} kg`}
          hint={s.co2_kg_per_position ? `${num(s.co2_kg_per_position, 2)} kg/position` : null}
        />
        <Metric
          icon={<Fuel size={16} />}
          tone="text-ink"
          label="Fuel"
          value={`${num(s.fuel_liters)} L`}
          hint={`${num(s.planned_distance_km)} km driven`}
        />
        <Metric
          icon={<Route size={16} />}
          tone="text-sky-600"
          label="Distance saved"
          value={`${num(s.distance_saved_km)} km`}
          hint={`baseline ${num(s.baseline_distance_km)} km`}
        />
      </div>

      {/* Friendly equivalences */}
      <div className="mt-3 flex flex-wrap gap-4 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
        <span className="inline-flex items-center gap-2">
          <TreePine size={16} /> ≈ {num(s.trees_year_equivalent, 1)} trees absorbing a year of CO₂
        </span>
        <span className="inline-flex items-center gap-2">
          <Car size={16} /> ≈ {num(s.car_km_equivalent)} km of car travel avoided
        </span>
      </div>

      {/* Pareto frontier */}
      {pareto ? (
        <div className="mt-5">
          <h3 className="text-sm font-semibold text-ink">Objective trade-off (cost ↔ CO₂ ↔ finish time)</h3>
          <p className="mb-3 text-xs text-muted">
            Greenest: <b className="capitalize">{pareto.recommendations?.greenest}</b> · Fastest:{' '}
            <b className="capitalize">{pareto.recommendations?.fastest}</b> · Cheapest:{' '}
            <b className="capitalize">{pareto.recommendations?.cheapest}</b>. Click a row to apply it.
          </p>
          <div className="space-y-2">
            {pareto.points.map((p) => {
              const meta = OBJECTIVES.find((o) => o.key === p.objective) || OBJECTIVES[1];
              const active = p.objective === currentObjective;
              return (
                <button
                  key={p.objective}
                  type="button"
                  onClick={() => applyObjective(p.objective)}
                  className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2 text-left transition hover:border-emerald-400 ${
                    active ? 'border-emerald-500 bg-emerald-50' : 'border-border bg-surface'
                  }`}
                >
                  <span className={`rounded-lg px-2 py-1 text-xs font-semibold ${TONE[meta.tone]}`}>
                    {meta.label}
                  </span>
                  <div className="flex-1">
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-emerald-500"
                        style={{ width: `${Math.round(((p.co2_kg || 0) / maxCo2) * 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="grid w-[58%] grid-cols-4 gap-2 text-right text-xs">
                    <span><span className="text-muted">CO₂ </span><b>{num(p.co2_kg)}kg</b></span>
                    <span><span className="text-muted">Cost </span><b>{num(p.cost_tnd)}</b></span>
                    <span><span className="text-muted">End </span><b>{p.finish_clock || '—'}</b></span>
                    <span><span className="text-muted">Trucks </span><b>{p.trucks_used}</b></span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function Metric({ icon, label, value, hint, tone }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <p className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted">
        {icon} {label}
      </p>
      <p className={`mt-1 text-xl font-semibold ${tone}`}>{value}</p>
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}
