"use client";
import { useState } from 'react';
import { ShieldAlert, X } from 'lucide-react';

export default function JustificationModal({ action, onConfirm, onCancel }) {
  const [reason, setReason] = useState('');

  function handleSubmit(e) {
    e.preventDefault();
    if (!reason.trim()) return;
    onConfirm(reason.trim());
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-[1.75rem] border border-[#e8e5df] bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="inline-flex rounded-2xl bg-amber-100 p-3 text-amber-600">
              <ShieldAlert size={20} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-600">Plan Verified</p>
              <h2 className="text-lg font-semibold text-[#1a1a2e]">Justification Required</h2>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full p-1.5 text-[#9e9aa4] transition hover:bg-[#f0eee9] hover:text-[#1a1a2e]"
          >
            <X size={16} />
          </button>
        </div>

        <p className="mb-1 text-xs font-semibold uppercase tracking-[0.15em] text-[#6b6b7b]">Requested action</p>
        <p className="mb-5 rounded-xl border border-[#ece8e1] bg-[#f8f7f3] px-3 py-2.5 text-sm font-medium text-[#1a1a2e]">
          {action}
        </p>

        <form onSubmit={handleSubmit}>
          <label className="mb-1.5 block text-sm font-semibold text-[#1a1a2e]">
            Reason for this change <span className="text-red-500">*</span>
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain why this modification is necessary after verification…"
            rows={3}
            className="w-full resize-none rounded-xl border border-[#e8e5df] bg-[#faf9f7] px-3 py-2.5 text-sm text-[#1a1a2e] outline-none transition focus:border-[#7c3aed] focus:ring-1 focus:ring-[#7c3aed]"
            autoFocus
          />
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-4 py-2 text-sm font-semibold text-[#1a1a2e] transition hover:bg-[#faf8f5]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!reason.trim()}
              className="inline-flex items-center gap-2 rounded-full bg-[#7c3aed] px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-[#6d28d9] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Submit &amp; Apply
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
