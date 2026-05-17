"use client";

import { useEffect, useState } from 'react';
import { getImpactPreview } from '../app/services/api';

const reasonOptions = [
  { value: 'vehicle_issue', label: '🚚 Vehicle issue' },
  { value: 'client_request', label: '📦 Client request change' },
  { value: 'time_constraint', label: '⏰ Time constraint' },
  { value: 'production_delay', label: '🏭 Production delay' },
  { value: 'logistics_constraint', label: '🌍 Logistics constraint' },
  { value: 'other', label: '❓ Other' },
];

export default function JustificationModal({ change, onConfirm, onCancel }) {
  const [impact, setImpact] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reasonCategory, setReasonCategory] = useState('');
  const [reasonText, setReasonText] = useState('');

  useEffect(() => {
    async function fetchImpact() {
      setLoading(true);
      try {
        const data = await getImpactPreview(change.planning_id, change.field, change.newValue);
        setImpact(data);
      } catch (error) {
        setImpact({
          affected_deliveries: 0,
          affected_routes: [],
          affected_drivers: [],
          estimated_delay_minutes: 0,
          warning: `Unable to load impact preview for ${change.field}.`,
        });
      } finally {
        setLoading(false);
      }
    }

    if (change) {
      fetchImpact();
      setReasonCategory('');
      setReasonText('');
    }
  }, [change]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4">
      <div className="w-full max-w-3xl rounded-[2rem] border border-amber-400/30 bg-slate-950 shadow-2xl shadow-black/50">
        <div className="rounded-t-[2rem] bg-amber-500/10 px-8 py-6">
          <h3 className="text-2xl font-semibold text-amber-100">Justification required</h3>
          <p className="mt-2 text-sm text-amber-100/85">This planning update must be reviewed before it can be applied.</p>
        </div>

        <div className="space-y-6 px-8 py-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-4">
              <p className="text-sm uppercase tracking-[0.22em] text-slate-500">Field</p>
              <p className="mt-2 text-base font-semibold text-slate-100">{change.field}</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-4">
              <p className="text-sm uppercase tracking-[0.22em] text-slate-500">Old value</p>
              <p className="mt-2 text-base text-slate-200">{change.oldValue}</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-4">
              <p className="text-sm uppercase tracking-[0.22em] text-slate-500">New value</p>
              <p className="mt-2 text-base text-slate-200">{change.newValue}</p>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-slate-500">Impact preview</p>
                <h4 className="mt-2 text-lg font-semibold text-slate-100">Estimated operational effect</h4>
              </div>
              <span className="rounded-full bg-amber-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-200">Preview</span>
            </div>

            {loading ? (
              <p className="mt-5 text-sm text-slate-400">Loading impact preview...</p>
            ) : (
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div className="rounded-3xl bg-slate-950/80 p-4">
                  <p className="text-sm text-slate-500">Deliveries affected</p>
                  <p className="mt-3 text-2xl font-semibold text-slate-100">{impact.affected_deliveries}</p>
                </div>
                <div className="rounded-3xl bg-slate-950/80 p-4">
                  <p className="text-sm text-slate-500">Routes impacted</p>
                  <p className="mt-3 text-base font-semibold text-slate-100">{impact.affected_routes.join(', ') || 'None'}</p>
                </div>
                <div className="rounded-3xl bg-slate-950/80 p-4">
                  <p className="text-sm text-slate-500">Drivers affected</p>
                  <p className="mt-3 text-base font-semibold text-slate-100">{impact.affected_drivers.join(', ') || 'None'}</p>
                </div>
                <div className="rounded-3xl bg-slate-950/80 p-4">
                  <p className="text-sm text-slate-500">Estimated delay</p>
                  <p className="mt-3 text-2xl font-semibold text-amber-300">{impact.estimated_delay_minutes} min</p>
                </div>
              </div>
            )}

            <div className="mt-5 rounded-3xl border border-amber-400/20 bg-amber-500/10 p-4 text-sm text-amber-100">
              {impact?.warning || 'Impact summary will appear here once loaded.'}
            </div>
          </div>

          <div className="grid gap-6">
            <label className="block">
              <span className="text-sm font-medium text-slate-300">Reason category</span>
              <select
                value={reasonCategory}
                onChange={(event) => setReasonCategory(event.target.value)}
                className="mt-3 w-full rounded-3xl border border-slate-800 bg-slate-950 p-3 text-slate-100 focus:border-amber-400 focus:outline-none"
              >
                <option value="">Select a reason</option>
                {reasonOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-sm font-medium text-slate-300">Additional comment (optional)</span>
              <textarea
                value={reasonText}
                onChange={(event) => setReasonText(event.target.value)}
                rows={4}
                className="mt-3 w-full resize-none rounded-3xl border border-slate-800 bg-slate-950 p-4 text-slate-100 outline-none focus:border-amber-400"
                placeholder="Add context for the justification"
              />
            </label>
          </div>
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-800 bg-slate-950/90 px-8 py-5 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-3xl border border-slate-700 px-6 py-3 text-sm text-slate-200 transition hover:bg-slate-800"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm({ reason_category: reasonCategory, reason_text: reasonText })}
            disabled={!reasonCategory}
            className="rounded-3xl bg-amber-400 px-6 py-3 text-sm font-semibold text-slate-950 transition disabled:cursor-not-allowed disabled:opacity-50"
          >
            Confirm & Apply
          </button>
        </div>
      </div>
    </div>
  );
}
