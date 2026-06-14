"use client";

import { useState } from 'react';
import { HelpCircle, Loader2, Lightbulb } from 'lucide-react';
import { explainTruck } from '../../app/services/api';

function num(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits });
}

/**
 * Explainable Routing panel.
 *
 * Pick a truck and get a grounded, plain-language rationale for its route:
 * peak utilisation, the binding constraint, hard-window and single-feasible
 * stops, and a right-sizing counterfactual — all derived from the plan, no
 * re-solve. Builds trust by showing the OR logic under the hood.
 */
export default function ExplainPanel({ plan }) {
  const activeTrucks = (plan?.trucks || []).filter((t) => t.trips && t.trips.length);
  const [truckId, setTruckId] = useState(activeTrucks[0]?.truck_id ?? '');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function explain() {
    if (truckId === '' || truckId === undefined) return;
    setLoading(true);
    setError(null);
    try {
      const res = await explainTruck(plan, truckId);
      setData(res);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Explain failed.');
    } finally {
      setLoading(false);
    }
  }

  if (!activeTrucks.length) return null;

  const f = data?.facts;

  return (
    <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-sky-100 text-sky-600">
            <HelpCircle size={18} />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-ink">Why this route?</h2>
            <p className="text-xs text-muted">Explainable routing — the reasoning behind a truck's plan.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={truckId}
            onChange={(e) => { setTruckId(e.target.value); setData(null); }}
            className="rounded-xl border border-border bg-surface px-3 py-2 text-sm text-ink"
          >
            {activeTrucks.map((t) => (
              <option key={t.truck_id} value={t.truck_id}>{t.truck_label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={explain}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Lightbulb size={16} />}
            Explain
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : null}

      {data ? (
        <div className="mt-5 space-y-4">
          <p className="rounded-xl bg-sky-50 px-4 py-3 text-sm leading-relaxed text-sky-900">{data.summary}</p>

          {f ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Fact label="Peak fill (pos)" value={`${num(f.peak_utilization_positions_pct, 0)}%`} />
              <Fact label="Peak fill (kg)" value={`${num(f.peak_utilization_kg_pct, 0)}%`} />
              <Fact label="Binding" value={f.binding_constraint} />
              <Fact label="Distance" value={`${num(f.total_km)} km`} />
              <Fact label="Trips / stops" value={`${f.trips} / ${f.stops}`} />
              <Fact label="Only-this-truck stops" value={num(f.single_feasible_stops)} />
              <Fact label="Hard-window stops" value={num(f.time_windowed_stops)} />
              <Fact label="Avg trip fill" value={`${num(f.avg_trip_utilization_positions_pct, 0)}%`} />
            </div>
          ) : null}

          {data.stop_reasons?.length ? (
            <div>
              <h3 className="text-sm font-semibold text-ink">Per-stop reasoning</h3>
              <div className="mt-2 space-y-1 text-sm">
                {data.stop_reasons.map((s, i) => (
                  <div key={i} className="flex flex-wrap items-baseline gap-2">
                    <span className="font-medium text-ink">{s.client}</span>
                    {s.eta ? <span className="text-xs text-muted">@ {s.eta}</span> : null}
                    <span className="text-muted">— {s.why}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function Fact({ label, value }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-base font-semibold capitalize text-ink">{value}</p>
    </div>
  );
}
