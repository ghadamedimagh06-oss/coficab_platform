"use client";
import { ClipboardList, ArrowRight } from 'lucide-react';

// Renders "old → new". When nothing changed (e.g. truck stays the same on a
// reschedule), show a muted "unchanged" instead of a redundant a → a.
function Change({ from, to }) {
  if (from === to) {
    return <span className="text-xs text-[#bcb8c2]">unchanged</span>;
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className="text-[#9b9bab] line-through">{from}</span>
      <ArrowRight size={12} className="shrink-0 text-amber-500" />
      <span className="font-semibold text-[#1a1a2e]">{to}</span>
    </span>
  );
}

const TH = ({ children, className = '' }) => (
  <th className={`whitespace-nowrap px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6b6b7b] ${className}`}>
    {children}
  </th>
);

const TD = ({ children, className = '' }) => (
  <td className={`px-3 py-2.5 text-sm text-[#1a1a2e] ${className}`}>
    {children}
  </td>
);

export default function PlanChangeLog({ entries }) {
  return (
    <div className="mt-8 space-y-4">
      <div className="flex items-center gap-3">
        <div className="inline-flex rounded-2xl bg-amber-100 p-2.5 text-amber-600">
          <ClipboardList size={16} />
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-600">Post-Verification</p>
          <h2 className="text-xl font-semibold text-[#1a1a2e]">Change Log</h2>
        </div>
      </div>

      {entries.length === 0 ? (
        <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-8 text-center text-sm text-[#9e9aa4]">
          No changes have been made since the plan was verified.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-[2rem] border border-amber-200 bg-white shadow-sm">
          <table className="min-w-full border-separate border-spacing-0">
            <thead className="sticky top-0 z-10 bg-amber-50">
              <tr className="border-b border-amber-200">
                <TH className="rounded-tl-[2rem] pl-6">#</TH>
                <TH>Logged at</TH>
                <TH>Client</TH>
                <TH>Action</TH>
                <TH>Truck change</TH>
                <TH>Time change</TH>
                <TH className="rounded-tr-[2rem] pr-6">Justification</TH>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => {
                const isLast = i === entries.length - 1;
                return (
                  <tr key={entry.id} className="transition-colors hover:bg-amber-50/40">
                    <TD className={`tabular-nums text-[#9b9bab] pl-6 ${isLast ? 'rounded-bl-[2rem]' : ''}`}>{i + 1}</TD>
                    <TD className="tabular-nums text-[#6b6b7b]">{entry.timestamp}</TD>
                    <TD className="font-medium">{entry.client}</TD>
                    <TD>
                      <span className="inline-block rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
                        {entry.action}
                      </span>
                    </TD>
                    <TD><Change from={entry.truckFrom} to={entry.truckTo} /></TD>
                    <TD><Change from={entry.timeFrom} to={entry.timeTo} /></TD>
                    <TD className={`max-w-xs pr-6 ${isLast ? 'rounded-br-[2rem]' : ''}`}>
                      <span className="block" title={entry.reason}>{entry.reason}</span>
                    </TD>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
