"use client";

import { useState } from 'react';
import { ShieldAlert, Loader2, TruckIcon, TrendingUp, AlertOctagon } from 'lucide-react';
import { runStressTest } from '../../app/services/api';

function num(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function deltaClass(v, goodWhenNegative = true) {
  if (v === null || v === undefined || v === 0) return 'text-muted';
  const bad = goodWhenNegative ? v > 0 : v < 0;
  return bad ? 'text-red-600' : 'text-emerald-600';
}

function signed(v, digits = 0) {
  if (v === null || v === undefined) return '—';
  const n = Number(v);
  return `${n > 0 ? '+' : ''}${num(n, digits)}`;
}

/**
 * Stress-Test Scenario Lab.
 *
 * Re-solves the day under disruption/growth scenarios (lose trucks, demand
 * spikes, no rental) and shows how fleet resilience holds up versus the baseline
 * — served %, unassigned load, cost & CO₂ deltas, and whether the rental gets
 * forced. Decision-support before the day actually breaks.
 */
export default function StressTestPanel({ day, activeTrucks, objective }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await runStressTest(day, { trucks: activeTrucks, objective });
      setData(res);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Stress test failed.');
    } finally {
      setLoading(false);
    }
  }

  const baseline = data?.baseline;

  return (
    <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-amber-100 text-amber-600">
            <ShieldAlert size={18} />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-ink">Stress-Test Scenario Lab</h2>
            <p className="text-xs text-muted">
              What if we lose trucks or demand spikes? Re-solves the day and compares to baseline.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={loading || !day}
          className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-amber-700 disabled:opacity-60"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <TrendingUp size={16} />}
          {loading ? 'Running scenarios…' : 'Run stress test'}
        </button>
      </div>

      {error ? (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : null}

      {loading && !data ? (
        <p className="mt-4 text-sm text-muted">
          Re-solving the day under each scenario… this runs the optimiser several times, so it
          takes ~30–40&nbsp;s.
        </p>
      ) : null}

      {baseline ? (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <th className="py-2 pr-3">Scenario</th>
                <th className="px-3 text-right">Served</th>
                <th className="px-3 text-right">Unassigned</th>
                <th className="px-3 text-right">Cost (TND)</th>
                <th className="px-3 text-right">CO₂ (kg)</th>
                <th className="px-3 text-right">Trucks</th>
                <th className="px-3 text-right">Finish</th>
                <th className="px-3 text-center">Rental?</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border bg-slate-50 font-medium">
                <td className="py-2 pr-3">Baseline (today)</td>
                <td className="px-3 text-right">{num(baseline.served_pct, 1)}%</td>
                <td className="px-3 text-right">{baseline.unassigned_count}</td>
                <td className="px-3 text-right">{num(baseline.cost_tnd)}</td>
                <td className="px-3 text-right">{num(baseline.co2_kg)}</td>
                <td className="px-3 text-right">{baseline.trucks_used}</td>
                <td className="px-3 text-right">{baseline.finish_clock || '—'}</td>
                <td className="px-3 text-center">{baseline.rental_used ? '⚠️' : '—'}</td>
              </tr>
              {data.scenarios.map((s, i) => (
                <tr key={i} className="border-b border-border">
                  <td className="py-2 pr-3">
                    <span className="flex items-center gap-1.5">
                      {!s.feasible ? <AlertOctagon size={14} className="text-red-600" /> : <TruckIcon size={14} className="text-muted" />}
                      {s.label}
                    </span>
                  </td>
                  {s.feasible ? (
                    <>
                      <td className="px-3 text-right">
                        {num(s.served_pct, 1)}%{' '}
                        <span className={`text-xs ${deltaClass(s.deltas.served_pct, false)}`}>
                          ({signed(s.deltas.served_pct, 1)})
                        </span>
                      </td>
                      <td className="px-3 text-right">
                        {s.unassigned_count}{' '}
                        <span className={`text-xs ${deltaClass(s.deltas.unassigned_count)}`}>
                          ({signed(s.deltas.unassigned_count)})
                        </span>
                      </td>
                      <td className="px-3 text-right">
                        {num(s.cost_tnd)}{' '}
                        <span className={`text-xs ${deltaClass(s.deltas.cost_tnd)}`}>
                          ({signed(s.deltas.cost_tnd)})
                        </span>
                      </td>
                      <td className="px-3 text-right">{num(s.co2_kg)}</td>
                      <td className="px-3 text-right">{s.trucks_used}</td>
                      <td className="px-3 text-right">{s.finish_clock || '—'}</td>
                      <td className="px-3 text-center">{s.rental_used ? '⚠️' : '—'}</td>
                    </>
                  ) : (
                    <td className="px-3 text-left text-xs text-red-600" colSpan={7}>
                      {s.note || 'Infeasible scenario.'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">
            Deltas are vs. baseline. Red = worse (more unassigned, higher cost, lower service).
          </p>
        </div>
      ) : null}
    </section>
  );
}
