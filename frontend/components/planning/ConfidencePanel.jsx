"use client";

import { useState } from 'react';
import { Activity, Loader2, Dice5, AlertTriangle, Clock } from 'lucide-react';
import { getPlanConfidence } from '../../app/services/api';

function num(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function otifTone(pct) {
  if (pct === null || pct === undefined) return 'text-muted';
  if (pct >= 90) return 'text-emerald-600';
  if (pct >= 70) return 'text-amber-600';
  return 'text-red-600';
}

function otifRing(pct) {
  if (pct >= 90) return 'border-emerald-500';
  if (pct >= 70) return 'border-amber-500';
  return 'border-red-500';
}

/**
 * Monte-Carlo Plan Confidence Score.
 *
 * Replays the current (possibly hand-edited) plan hundreds of times under
 * randomised travel/service times and rare disruptions, then reports the
 * expected OTIF, how reliable the plan is, the finish-time spread, and which
 * stops are most fragile — turning a deterministic plan into a risk-aware one.
 */
export default function ConfidencePanel({ plan, day, objective }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      // Send the on-screen plan so we simulate exactly what's shown (no rebuild).
      const res = await getPlanConfidence(day, { plan, objective, runs: 500 });
      setReport(res.confidence);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Simulation failed.');
    } finally {
      setLoading(false);
    }
  }

  const otif = report?.expected_otif_pct;

  return (
    <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-100 text-indigo-600">
            <Activity size={18} />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-ink">Plan Confidence (Monte-Carlo)</h2>
            <p className="text-xs text-muted">
              Simulates the day 500× under traffic &amp; delay noise — how robust is this plan, really?
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={loading || !plan}
          className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-60"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Dice5 size={16} />}
          {loading ? 'Simulating…' : 'Run simulation'}
        </button>
      </div>

      {error ? (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : null}

      {report ? (
        <div className="mt-5 grid gap-5 lg:grid-cols-[auto_1fr]">
          {/* Headline gauge */}
          <div className="flex items-center gap-4">
            <div className={`flex h-28 w-28 flex-col items-center justify-center rounded-full border-8 ${otifRing(otif)}`}>
              <span className={`text-3xl font-bold ${otifTone(otif)}`}>{num(otif, 0)}%</span>
              <span className="text-[10px] uppercase tracking-wide text-muted">exp. OTIF</span>
            </div>
            <div className="text-sm">
              <p className="text-muted">Reliable (≥{num(report.otif_target_pct)}% OTIF) on</p>
              <p className="text-2xl font-semibold text-ink">{num(report.confidence_pct, 1)}%</p>
              <p className="text-muted">of {num(report.runs)} simulated days</p>
            </div>
          </div>

          {/* Detail metrics */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Metric label="Perfect days" value={`${num(report.all_ontime_pct, 1)}%`} />
            <Metric label="Worst-case OTIF (P10)" value={`${num(report.otif_p10_pct, 1)}%`} />
            <Metric label="Stops simulated" value={num(report.stops_simulated)} />
            <Metric icon={<Clock size={13} />} label="Finish P50" value={report.finish_p50 || '—'} />
            <Metric icon={<Clock size={13} />} label="Finish P90" value={report.finish_p90 || '—'} />
            <Metric icon={<Clock size={13} />} label="Finish worst" value={report.finish_worst || '—'} />
          </div>

          {/* Fragile stops */}
          {report.fragile_stops?.length ? (
            <div className="lg:col-span-2">
              <h3 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                <AlertTriangle size={14} className="text-amber-600" /> Most fragile stops
              </h3>
              <div className="mt-2 space-y-1.5">
                {report.fragile_stops.filter((f) => f.late_pct > 0).slice(0, 5).map((f) => (
                  <div key={f.stop} className="flex items-center gap-3 text-sm">
                    <span className="w-64 truncate text-ink" title={f.stop}>{f.stop}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className={`h-full rounded-full ${f.late_pct >= 50 ? 'bg-red-500' : 'bg-amber-500'}`}
                        style={{ width: `${Math.min(100, f.late_pct)}%` }}
                      />
                    </div>
                    <span className="w-16 text-right font-medium text-muted">{num(f.late_pct, 0)}% late</span>
                  </div>
                ))}
                {report.fragile_stops.every((f) => f.late_pct === 0) ? (
                  <p className="text-sm text-emerald-600">No fragile stops — every delivery held up across all runs. 🎉</p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function Metric({ icon, label, value }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <p className="flex items-center gap-1 text-xs uppercase tracking-wide text-muted">{icon}{label}</p>
      <p className="mt-1 text-lg font-semibold text-ink">{value}</p>
    </div>
  );
}
