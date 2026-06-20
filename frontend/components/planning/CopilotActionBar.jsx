"use client";

import { useState } from 'react';
import { Sparkles, Loader2, CheckCircle2, ArrowRight, AlertTriangle, CornerDownLeft } from 'lucide-react';
import { copilotAction } from '../../app/services/api';

const SUGGESTIONS = ['summary', 'explain truck 5', 'truck 3 broke down, replan'];

/**
 * Agentic Optiroute command bar (W3.1).
 *
 * Type a plain-language instruction — "summary", "explain truck 5",
 * "truck 3 broke down, replan" — and Optiroute returns a grounded PROPOSAL.
 * Read-only proposals (summary / explain) are shown inline; a breakdown recovery
 * comes with an "Apply recovery" button that swaps the live plan. Works with or
 * without the Groq LLM configured (the action engine is deterministic).
 */
export default function CopilotActionBar({ plan, day, onApplyPlan }) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [proposal, setProposal] = useState(null);
  const [error, setError] = useState(null);
  const [applied, setApplied] = useState(false);

  async function run(command) {
    const q = (command ?? text).trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setApplied(false);
    setProposal(null);
    try {
      const res = await copilotAction(q, { plan, day, objective: plan?.objective });
      setProposal(res);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Optiroute could not handle that.');
    } finally {
      setLoading(false);
    }
  }

  function apply() {
    if (proposal?.plan && onApplyPlan) {
      onApplyPlan(proposal.plan);
      setApplied(true);
    }
  }

  const diff = proposal?.diff;
  const facts = proposal?.explain?.facts;

  return (
    <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-violet-100 text-violet-600">
          <Sparkles size={18} />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-ink">Ask Optiroute to act</h2>
          <p className="text-xs text-muted">
            Plain language → a grounded proposal you approve. e.g. “truck 3 broke down, replan”.
          </p>
        </div>
      </div>

      <form
        className="mt-4 flex items-center gap-2"
        onSubmit={(e) => { e.preventDefault(); run(); }}
      >
        <div className="relative flex-1">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Tell Optiroute what to do…"
            className="w-full rounded-xl border border-border bg-surface px-3 py-2 pr-9 text-sm text-ink outline-none focus:border-violet-400"
          />
          <CornerDownLeft size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted" />
        </div>
        <button
          type="submit"
          disabled={loading || !text.trim()}
          className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
          {loading ? 'Thinking…' : 'Run'}
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => { setText(s); run(s); }}
            className="rounded-full border border-border px-2.5 py-0.5 text-[11px] text-muted transition hover:border-violet-300 hover:text-violet-700"
          >
            {s}
          </button>
        ))}
      </div>

      {error ? <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

      {proposal ? (
        <div className="mt-4 rounded-xl border border-border bg-surface p-4">
          {proposal.title ? <h3 className="text-sm font-semibold text-ink">{proposal.title}</h3> : null}
          <p className="mt-1 text-sm text-muted">{proposal.summary}</p>

          {/* Explain facts */}
          {facts ? (
            <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(facts).slice(0, 6).map(([k, v]) => (
                <div key={k} className="rounded-lg border border-border bg-white p-2">
                  <dt className="text-[10px] uppercase tracking-wide text-muted">{k.replace(/_/g, ' ')}</dt>
                  <dd className="text-sm font-semibold text-ink">{String(v)}</dd>
                </div>
              ))}
            </dl>
          ) : null}

          {/* Replan diff + apply */}
          {diff ? (
            <div className="mt-3">
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge tone="text-amber-700 bg-amber-50">{diff.reassigned_count} reassigned</Badge>
                <Badge tone="text-emerald-700 bg-emerald-50">{diff.recovered_count} recovered</Badge>
                <Badge tone={diff.newly_unassigned_count ? 'text-red-700 bg-red-50' : 'text-muted bg-white'}>
                  {diff.newly_unassigned_count} now unassigned
                </Badge>
                {diff.cost_delta_tnd != null ? (
                  <Badge tone="text-muted bg-white">Cost Δ {diff.cost_delta_tnd > 0 ? '+' : ''}{Math.round(diff.cost_delta_tnd)} TND</Badge>
                ) : null}
              </div>
              {diff.newly_unassigned_count ? (
                <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-800">
                  <AlertTriangle size={13} /> Some deliveries can’t be served by the reduced fleet.
                </p>
              ) : null}
            </div>
          ) : null}

          {proposal.applies && proposal.plan ? (
            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                onClick={apply}
                disabled={applied}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:opacity-60"
              >
                <CheckCircle2 size={16} /> {applied ? 'Applied' : 'Apply recovery plan'}
              </button>
              {applied ? <span className="text-sm text-emerald-600">The live plan now reflects the recovery.</span> : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function Badge({ children, tone }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 font-medium ${tone}`}><ArrowRight size={11} />{children}</span>;
}
