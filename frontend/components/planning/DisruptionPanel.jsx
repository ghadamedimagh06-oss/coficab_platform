"use client";

import { useState } from 'react';
import { Wrench, Loader2, ArrowRight, AlertTriangle, CheckCircle2, RotateCcw } from 'lucide-react';
import { replanPlan } from '../../app/services/api';

function num(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function signed(v, digits = 0) {
  if (v === null || v === undefined) return '—';
  const n = Number(v);
  return `${n > 0 ? '+' : ''}${num(n, digits)}`;
}

/**
 * Self-Healing Disruption panel.
 *
 * Simulate a breakdown: take one or more trucks out of service, re-optimise the
 * remaining undelivered stops across the remaining fleet, and review the recovery
 * diff (reassignments, newly-unassigned, recovered, cost & CO₂ deltas) before
 * applying it to the live plan with one click.
 */
export default function DisruptionPanel({ plan, day, onApplyPlan }) {
  const [broken, setBroken] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [applied, setApplied] = useState(false);

  const activeTrucks = (plan?.trucks || []).filter((t) => t.trips && t.trips.length);

  function toggle(id) {
    setApplied(false);
    setResult(null);
    setBroken((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  async function replan() {
    if (!broken.length) return;
    setLoading(true);
    setError(null);
    setApplied(false);
    try {
      const res = await replanPlan(day, {
        plan,
        disruptedTruckIds: broken,
        objective: plan.objective,
      });
      setResult(res);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Re-plan failed.');
    } finally {
      setLoading(false);
    }
  }

  function apply() {
    if (result?.plan && onApplyPlan) {
      onApplyPlan(result.plan);
      setApplied(true);
    }
  }

  const diff = result?.diff;

  return (
    <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-rose-100 text-rose-600">
          <Wrench size={18} />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-ink">Self-Healing Disruption</h2>
          <p className="text-xs text-muted">
            A truck breaks down? Take it out and re-optimise the rest of the day instantly.
          </p>
        </div>
      </div>

      {/* Truck selector */}
      <div className="mt-4 flex flex-wrap gap-2">
        {activeTrucks.map((t) => {
          const on = broken.includes(t.truck_id);
          return (
            <button
              key={t.truck_id}
              type="button"
              onClick={() => toggle(t.truck_id)}
              className={`rounded-xl border px-3 py-1.5 text-sm font-medium transition ${
                on ? 'border-rose-500 bg-rose-50 text-rose-700' : 'border-border bg-surface text-ink hover:border-rose-300'
              }`}
            >
              {on ? '🔧 ' : ''}{t.truck_label}
            </button>
          );
        })}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={replan}
          disabled={loading || !broken.length}
          className="inline-flex items-center gap-2 rounded-xl bg-rose-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-rose-700 disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Wrench size={16} />}
          {loading ? 'Re-optimising…' : `Break down ${broken.length || ''} & re-plan`}
        </button>
        {broken.length ? (
          <button
            type="button"
            onClick={() => { setBroken([]); setResult(null); setApplied(false); }}
            className="inline-flex items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-sm text-muted hover:bg-surface"
          >
            <RotateCcw size={14} /> Reset
          </button>
        ) : null}
      </div>

      {error ? (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : null}

      {diff ? (
        <div className="mt-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Re-planned stops" value={num(diff.replanned_stops)} />
            <Stat label="Reassigned" value={num(diff.reassigned_count)} tone="text-amber-600" />
            <Stat label="Newly unassigned" value={num(diff.newly_unassigned_count)} tone={diff.newly_unassigned_count ? 'text-red-600' : 'text-emerald-600'} />
            <Stat label="Recovered" value={num(diff.recovered_count)} tone="text-emerald-600" />
            <Stat label="Cost Δ (TND)" value={signed(diff.cost_delta_tnd)} tone={diff.cost_delta_tnd > 0 ? 'text-red-600' : 'text-emerald-600'} />
            <Stat label="CO₂ Δ (kg)" value={signed(diff.co2_delta_kg)} tone="text-muted" />
          </div>

          {diff.reassignments?.length ? (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-ink">Reassignments</h3>
              <div className="mt-2 space-y-1 text-sm">
                {diff.reassignments.slice(0, 8).map((r) => (
                  <div key={r.stop_id} className="flex items-center gap-2 text-muted">
                    <span className="font-medium text-ink">#{r.stop_id}</span>
                    <span className="line-through">{r.from}</span>
                    <ArrowRight size={14} />
                    <span className="font-medium text-emerald-600">{r.to}</span>
                  </div>
                ))}
                {diff.reassignments.length > 8 ? (
                  <p className="text-xs text-muted">…and {diff.reassignments.length - 8} more.</p>
                ) : null}
              </div>
            </div>
          ) : null}

          {diff.newly_unassigned_count ? (
            <p className="mt-3 flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              <AlertTriangle size={15} />
              {diff.newly_unassigned_count} delivery(ies) can no longer be served by the reduced fleet —
              consider a rental or splitting across tomorrow.
            </p>
          ) : null}

          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={apply}
              disabled={applied}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
            >
              <CheckCircle2 size={16} />
              {applied ? 'Recovery applied' : 'Apply recovery plan'}
            </button>
            {applied ? <span className="text-sm text-emerald-600">The live plan now reflects the recovery.</span> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function Stat({ label, value, tone = 'text-ink' }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${tone}`}>{value}</p>
    </div>
  );
}
