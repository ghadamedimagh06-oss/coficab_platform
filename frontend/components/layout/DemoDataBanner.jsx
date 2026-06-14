"use client";

import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { getSourceStatus } from '../../app/services/api';

/**
 * Persistent, honest data-provenance banner.
 *
 * Shows a sticky warning whenever the platform is NOT serving live database
 * data (i.e. it has fallen back to the Excel workbook or to built-in mock data),
 * so a jury or operator can never mistake demo/fabricated numbers for real ones.
 * Stays silent when the source is the live database.
 */
export default function DemoDataBanner() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const s = await getSourceStatus();
        if (!cancelled) setStatus(s);
      } catch {
        if (!cancelled) setStatus(null);
      }
    }
    check();
    // Re-check periodically so the banner clears once the DB is wired in.
    const id = setInterval(check, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!status || status.is_live) return null;

  const isMock = status.source === 'mock';
  const label = isMock ? 'DEMO DATA — not real' : 'FILE DATA — read from Excel, not the live database';
  const detail = isMock
    ? 'No database or workbook is connected; figures shown are illustrative mock values.'
    : `Serving "${status.file_name || 'weekly planning'}" parsed from the workbook. Connect Postgres for live operational data.`;

  return (
    <div
      role="status"
      className={`sticky top-0 z-40 flex items-center gap-2 px-4 py-2 text-sm font-medium ${
        isMock ? 'bg-amber-500 text-amber-950' : 'bg-sky-500/90 text-sky-950'
      }`}
    >
      <AlertTriangle size={16} className="shrink-0" />
      <span className="font-semibold">{label}.</span>
      <span className="hidden truncate opacity-90 sm:inline">{detail}</span>
    </div>
  );
}
