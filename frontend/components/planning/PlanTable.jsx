"use client";

import { Download } from 'lucide-react';

const STATUS_STYLE = {
  planned:   'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  new:       'bg-sky-50 text-sky-700 ring-1 ring-sky-200',
  cancelled: 'bg-slate-100 text-slate-500 ring-1 ring-slate-200',
  urgent:    'bg-red-50 text-red-700 ring-1 ring-red-200',
};

const PRIORITY_STYLE = {
  urgent: 'text-red-600 font-semibold',
  high:   'text-amber-600 font-semibold',
  normal: 'text-[#6b6b7b]',
  low:    'text-[#9b9bab]',
};

function fmt(n) {
  return n == null || n === '' ? '—' : Number(n).toLocaleString();
}

function Badge({ value, styles }) {
  const cls = styles[value] || 'bg-[#f0eee9] text-[#6b6b7b] ring-1 ring-[#e8e5df]';
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium capitalize ${cls}`}>
      {value || '—'}
    </span>
  );
}

// Shown on deliveries the optimizer auto-split. The full explanation (original
// positions, truck capacity, resulting parts) is on hover via the title.
function SplitBadge({ row }) {
  const counter = row.split_total_parts ? ` ${row.split_part}/${row.split_total_parts}` : '';
  return (
    <span
      title={row.planning_comment || 'Auto-split delivery'}
      className="shrink-0 cursor-help rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800 ring-1 ring-amber-300"
    >
      🔀 Auto-split{counter}
    </span>
  );
}

// Flatten plan into export-shaped rows, grouped truck→trip→stop then unassigned.
function buildRows(plan) {
  if (!plan) return [];
  const dayLabel = plan.day
    ? new Date(plan.day + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })
    : '—';
  const weekday = plan.day
    ? new Date(plan.day + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'long' })
    : '';

  const rows = [];

  (plan.trucks || []).forEach((truck) => {
    (truck.trips || []).forEach((trip, tripIdx) => {
      (trip.stops || []).forEach((stop, stopIdx) => {
        const raw = stop.raw || {};
        const constraints = stop.constraints || {};
        rows.push({
          _key: `${truck.truck_id}-${trip.trip_id}-${stop.id}`,
          _truck: truck,
          _trip: trip,
          _firstInTrip: stopIdx === 0,
          _tripStops: trip.stops.length,
          _firstInTruck: tripIdx === 0 && stopIdx === 0,
          _truckTrips: truck.trips.length,
          delivery_day: raw.delivery_day || weekday,
          row_number: raw.row_number || stop.id,
          vehicle: truck.truck_label,
          driver: constraints.required_driver || raw.driver || '—',
          etd: stop.etd || '—',
          eta: stop.eta || '—',
          status: stop.status || 'planned',
          client: stop.client || '—',
          end_location: stop.resolved_location || stop.end_location || '—',
          position_count: stop.quantity_positions ?? stop.position_count,
          gross_weight_kg: stop.quantity_kg,
          priority: stop.priority || 'normal',
          comments: stop.planning_comment || constraints.notes || constraints.comment_constraint || raw.notes || '',
          is_split: !!stop.is_split,
          planning_comment: stop.planning_comment || '',
          split_part: stop.split_part,
          split_total_parts: stop.split_total_parts,
          travel_min: stop.travel_min,
          service_min: stop.service_min,
          distance_km: stop.distance_km,
          _unassigned: false,
        });
      });
    });
  });

  (plan.unassigned || []).forEach((stop) => {
    const raw = stop.raw || {};
    const constraints = stop.constraints || {};
    rows.push({
      _key: `unassigned-${stop.id}`,
      _truck: null,
      _trip: null,
      _firstInTrip: true,
      _tripStops: 1,
      _firstInTruck: true,
      _truckTrips: 1,
      delivery_day: raw.delivery_day || weekday,
      row_number: raw.row_number || stop.id,
      vehicle: '—',
      driver: '—',
      etd: stop.etd || '—',
      eta: stop.eta || '—',
      status: stop.status || 'unassigned',
      client: stop.client || '—',
      end_location: stop.resolved_location || stop.end_location || '—',
      position_count: stop.quantity_positions ?? stop.position_count,
      gross_weight_kg: stop.quantity_kg,
      priority: stop.priority || 'normal',
      comments: stop.unassigned_reason || stop.planning_comment || constraints.comment_constraint || '',
      is_split: !!stop.is_split,
      planning_comment: stop.planning_comment || '',
      split_part: stop.split_part,
      split_total_parts: stop.split_total_parts,
      travel_min: null,
      service_min: null,
      distance_km: stop.distance_km,
      _unassigned: true,
    });
  });

  return rows;
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

export default function PlanTable({ plan, onExport, exporting }) {
  const rows = buildRows(plan);
  const assigned = rows.filter((r) => !r._unassigned);
  const unassigned = rows.filter((r) => r._unassigned);

  if (!plan) return null;

  const totalPos = assigned.reduce((s, r) => s + Number(r.position_count || 0), 0);
  const totalKg  = assigned.reduce((s, r) => s + Number(r.gross_weight_kg || 0), 0);

  return (
    <div className="mt-8 space-y-4">
      {/* header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#7c3aed]">Delivery schedule</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1a1a2e]">
            Export-ready plan table
          </h2>
          <p className="mt-0.5 text-xs text-[#6b6b7b]">
            {assigned.length} deliveries · {fmt(totalPos)} positions · {fmt(Math.round(totalKg))} kg loaded
            {unassigned.length > 0 && ` · ${unassigned.length} unassigned`}
          </p>
        </div>
        {onExport && (
          <button
            type="button"
            onClick={onExport}
            disabled={exporting || !plan?.source_file}
            className="inline-flex items-center gap-2 rounded-full bg-[#7c3aed] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#6d28d9] disabled:opacity-50"
          >
            <Download size={15} />
            {exporting ? 'Exporting…' : 'Export to Excel'}
          </button>
        )}
      </div>

      {/* main table */}
      <div className="overflow-x-auto rounded-[2rem] border border-[#e8e5df] bg-white shadow-sm">
        <table className="min-w-full border-separate border-spacing-0">
          <thead className="sticky top-0 z-10 bg-[#f8f7f3]">
            <tr className="border-b border-[#e8e5df]">
              <TH className="rounded-tl-[2rem] pl-6">Day</TH>
              <TH>N°</TH>
              <TH>Truck</TH>
              <TH>Trip</TH>
              <TH>Driver</TH>
              <TH>Client</TH>
              <TH>Destination</TH>
              <TH>ETD</TH>
              <TH>ETA</TH>
              <TH>Travel</TH>
              <TH>Dist km</TH>
              <TH>Positions</TH>
              <TH>Gross kg</TH>
              <TH>Priority</TH>
              <TH>Status</TH>
              <TH className="rounded-tr-[2rem] pr-6">Comments / Reason</TH>
            </tr>
          </thead>
          <tbody>
            {/* assigned rows grouped by truck */}
            {assigned.map((row, i) => {
              const isLastRow = i === assigned.length - 1 && unassigned.length === 0;
              return (
                <tr
                  key={row._key}
                  className={`transition-colors hover:bg-[#faf8f5] ${
                    row._firstInTrip && i > 0 ? 'border-t border-dashed border-[#e8e5df]' : ''
                  }`}
                >
                  <TD className={`pl-6 text-[#6b6b7b] ${isLastRow ? 'rounded-bl-[2rem]' : ''}`}>
                    {row.delivery_day || '—'}
                  </TD>
                  <TD className="tabular-nums text-[#9b9bab]">{row.row_number ?? '—'}</TD>
                  <TD>
                    {row._firstInTruck ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-[#e8e5df] bg-white px-2.5 py-0.5 text-xs font-semibold text-[#1a1a2e] shadow-sm">
                        <span className="h-2 w-2 rounded-full bg-[#7c3aed]" />
                        {row.vehicle}
                      </span>
                    ) : (
                      <span className="pl-4 text-xs text-[#9b9bab]">{row.vehicle}</span>
                    )}
                  </TD>
                  <TD className="text-xs text-[#9b9bab]">
                    {row._trip ? (
                      <span title={`Depart ${row._trip.depart_at} → return ${row._trip.return_at}`}>
                        {row._trip.trip_id.replace(/^\d+-/, '')} · {row._trip.depart_at}–{row._trip.return_at}
                      </span>
                    ) : '—'}
                  </TD>
                  <TD className="text-[#6b6b7b]">{row.driver}</TD>
                  <TD className="max-w-[14rem] font-medium">
                    <span className="flex items-center gap-1.5">
                      <span className="truncate" title={row.client}>{row.client}</span>
                      {row.is_split && <SplitBadge row={row} />}
                    </span>
                  </TD>
                  <TD className="max-w-[12rem] text-xs text-[#6b6b7b]">
                    <span className="block truncate" title={row.end_location}>{row.end_location}</span>
                  </TD>
                  <TD className="tabular-nums font-medium text-[#7c3aed]">{row.etd}</TD>
                  <TD className="tabular-nums font-medium text-[#6b6b7b]">{row.eta}</TD>
                  <TD className="tabular-nums text-[#6b6b7b]">
                    {row.travel_min != null ? `${row.travel_min} min` : '—'}
                  </TD>
                  <TD className="tabular-nums text-[#6b6b7b]">
                    {row.distance_km != null ? row.distance_km : '—'}
                  </TD>
                  <TD className="tabular-nums font-semibold">{fmt(row.position_count)}</TD>
                  <TD className="tabular-nums text-[#6b6b7b]">{fmt(row.gross_weight_kg)}</TD>
                  <TD>
                    <span className={`text-sm ${PRIORITY_STYLE[row.priority] || PRIORITY_STYLE.normal}`}>
                      {row.priority}
                    </span>
                  </TD>
                  <TD><Badge value={row.status} styles={STATUS_STYLE} /></TD>
                  <TD className={`max-w-[16rem] text-xs text-[#6b6b7b] pr-6 ${isLastRow ? 'rounded-br-[2rem]' : ''}`}>
                    <span className="block truncate" title={row.comments}>{row.comments || ''}</span>
                  </TD>
                </tr>
              );
            })}

            {/* totals row */}
            {assigned.length > 0 && (
              <tr className="border-t-2 border-[#e8e5df] bg-[#f8f7f3] font-semibold">
                <TD className="pl-6 text-[#6b6b7b]" />
                <TD />
                <TD />
                <TD />
                <TD />
                <TD className="text-xs uppercase tracking-wider text-[#6b6b7b]">
                  {assigned.length} deliveries
                </TD>
                <TD />
                <TD />
                <TD />
                <TD />
                <TD />
                <TD className="tabular-nums text-[#1a1a2e]">{fmt(totalPos)}</TD>
                <TD className="tabular-nums text-[#1a1a2e]">{fmt(Math.round(totalKg))}</TD>
                <TD />
                <TD />
                <TD className="pr-6" />
              </tr>
            )}

            {/* unassigned rows */}
            {unassigned.length > 0 && (
              <>
                <tr>
                  <td colSpan={16} className="border-t-2 border-dashed border-red-200 bg-red-50 px-6 py-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.18em] text-red-600">
                      Needs dispatcher review — {unassigned.length} unassigned
                    </span>
                  </td>
                </tr>
                {unassigned.map((row, i) => {
                  const isLast = i === unassigned.length - 1;
                  return (
                    <tr key={row._key} className="bg-red-50/40 hover:bg-red-50 transition-colors">
                      <TD className={`pl-6 text-[#6b6b7b] ${isLast ? 'rounded-bl-[2rem]' : ''}`}>
                        {row.delivery_day || '—'}
                      </TD>
                      <TD className="tabular-nums text-[#9b9bab]">{row.row_number ?? '—'}</TD>
                      <TD>
                        <span className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-white px-2.5 py-0.5 text-xs font-semibold text-red-600">
                          <span className="h-2 w-2 rounded-full bg-red-400" />
                          Unassigned
                        </span>
                      </TD>
                      <TD className="text-xs text-[#9b9bab]">—</TD>
                      <TD className="text-[#6b6b7b]">—</TD>
                      <TD className="max-w-[14rem] font-medium text-red-700">
                        <span className="flex items-center gap-1.5">
                          <span className="truncate" title={row.client}>{row.client}</span>
                          {row.is_split && <SplitBadge row={row} />}
                        </span>
                      </TD>
                      <TD className="max-w-[12rem] text-xs text-[#6b6b7b]">
                        <span className="block truncate" title={row.end_location}>{row.end_location}</span>
                      </TD>
                      <TD className="tabular-nums text-[#9b9bab]">{row.etd}</TD>
                      <TD className="tabular-nums text-[#9b9bab]">{row.eta}</TD>
                      <TD>—</TD>
                      <TD className="tabular-nums text-[#6b6b7b]">
                        {row.distance_km != null ? row.distance_km : '—'}
                      </TD>
                      <TD className="tabular-nums font-semibold text-red-700">{fmt(row.position_count)}</TD>
                      <TD className="tabular-nums text-[#6b6b7b]">{fmt(row.gross_weight_kg)}</TD>
                      <TD>
                        <span className={`text-sm ${PRIORITY_STYLE[row.priority] || PRIORITY_STYLE.normal}`}>
                          {row.priority}
                        </span>
                      </TD>
                      <TD><Badge value="unassigned" styles={STATUS_STYLE} /></TD>
                      <TD className={`max-w-[20rem] text-xs text-red-600 pr-6 ${isLast ? 'rounded-br-[2rem]' : ''}`}>
                        <span className="block truncate" title={row.comments}>{row.comments}</span>
                      </TD>
                    </tr>
                  );
                })}
              </>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
