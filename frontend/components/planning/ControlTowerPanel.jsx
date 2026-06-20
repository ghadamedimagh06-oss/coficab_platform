"use client";

import { useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { Radio, Loader2, AlertTriangle, Clock, RotateCcw, Gauge, Zap } from 'lucide-react';
import { getControlTower } from '../../app/services/api';

// react-leaflet touches `window` at import time, so the map is loaded
// client-side only (mirrors how RouteMap is mounted on the page).
const ControlTowerMap = dynamic(() => import('./ControlTowerMap'), {
  ssr: false,
  loading: () => (
    <div className="flex h-[480px] w-full items-center justify-center rounded-[1.25rem] border border-[#ece8e1] bg-[#f0eee9] text-sm text-[#9e9aa4]">
      Loading map…
    </div>
  ),
});

// Per-truck route colours — must match ControlTowerMap's ROUTE_PALETTE so the
// filter chips and the map routes agree.
const ROUTE_PALETTE = [
  '#7c3aed', '#2563eb', '#059669', '#d97706', '#dc2626', '#0891b2', '#9333ea', '#65a30d',
];

const STATE_COLOR = {
  en_route: '#2563eb',
  at_stop: '#059669',
  returning: '#7c3aed',
  reloading: '#d97706',
  idle: '#9ca3af',
  completed: '#64748b',
};

function toMin(value) {
  if (value == null) return null;
  const [h, m] = String(value).split(':');
  const hh = Number(h);
  const mm = Number(m || 0);
  return Number.isFinite(hh) ? hh * 60 + mm : null;
}

function clock(min) {
  if (min == null) return '—';
  const m = Math.max(0, Math.round(min));
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}

function dayBounds(plan) {
  let start = Infinity;
  let end = -Infinity;
  (plan?.trucks || []).forEach((t) => (t.trips || []).forEach((trip) => {
    const d = toMin(trip.depart_at);
    const r = toMin(trip.return_at);
    if (d != null) start = Math.min(start, d);
    if (r != null) end = Math.max(end, r);
  }));
  if (!Number.isFinite(start) || !Number.isFinite(end)) return [6 * 60, 20 * 60];
  return [start, end];
}

/**
 * Live Control Tower.
 *
 * Plays the day forward: a clock slider interpolates every truck's current
 * position along its planned route, colour-coded by live state, on a live map.
 * Inject a delay on any truck and watch which downstream drops blow their
 * delivery window — the predicted-late / geofence alerts turn red before the
 * customer ever notices. All derived from the current plan (no GPS feed).
 */
export default function ControlTowerPanel({ plan, day, selectedTruckId = null, onSelectTruck }) {
  const [start, end] = useMemo(() => dayBounds(plan), [plan]);
  const [asOf, setAsOf] = useState(null);          // minutes; null → server midpoint
  const [delays, setDelays] = useState({});         // { [truckId]: minutes }
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const reqId = useRef(0);

  // Trucks with routed work, tagged with their route colour + stop count for the
  // filter chips. Colour is keyed by index in plan.trucks to match the map.
  const routeChips = useMemo(() => (
    (plan?.trucks || [])
      .map((t, ti) => ({
        truck_id: t.truck_id,
        truck_label: t.truck_label,
        color: ROUTE_PALETTE[ti % ROUTE_PALETTE.length],
        stops: (t.trips || []).reduce((n, trip) => n + (trip.stops || []).length, 0),
      }))
      .filter((t) => t.stops > 0)
  ), [plan]);

  const activeTrucks = (plan?.trucks || []).filter((t) => t.trips && t.trips.length);

  // Reset the clock when the plan changes so the slider tracks the new day.
  useEffect(() => { setAsOf(null); setDelays({}); }, [plan?.plan_id]);

  useEffect(() => {
    if (!plan || !activeTrucks.length) { setSnapshot(null); return; }
    const id = ++reqId.current;
    setLoading(true);
    setError(null);
    const delayList = Object.entries(delays)
      .filter(([, m]) => Number(m) > 0)
      .map(([truck_id, delay_min]) => ({ truck_id: Number(truck_id), delay_min: Number(delay_min) }));
    getControlTower(day, {
      plan,
      asOf: asOf == null ? undefined : clock(asOf),
      delays: delayList,
      objective: plan.objective,
    })
      .then((res) => {
        if (id !== reqId.current) return;          // ignore stale responses
        const snap = res.control_tower;
        setSnapshot(snap);
        if (asOf == null && snap?.as_of_minutes != null) setAsOf(snap.as_of_minutes);
      })
      .catch((err) => {
        if (id !== reqId.current) return;
        setError(err?.response?.data?.detail || err.message || 'Could not load the control tower.');
      })
      .finally(() => { if (id === reqId.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan, day, asOf, delays]);

  function bumpDelay(truckId, by) {
    setDelays((cur) => {
      const next = Math.max(0, (Number(cur[truckId]) || 0) + by);
      return { ...cur, [truckId]: next };
    });
  }

  if (!activeTrucks.length) {
    return (
      <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
        <Header />
        <p className="mt-4 text-sm text-muted">Generate a plan with at least one routed truck to open the control tower.</p>
      </section>
    );
  }

  const fleet = snapshot?.fleet;
  const sliderValue = asOf == null ? Math.round((start + end) / 2) : asOf;

  return (
    <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
      <Header />

      {/* Clock scrubber */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-xs text-muted">
          <span className="inline-flex items-center gap-1.5"><Clock size={13} /> Time of day</span>
          <span className="tabular-nums text-base font-semibold text-ink">{snapshot?.as_of || clock(sliderValue)}</span>
        </div>
        <input
          type="range"
          min={start}
          max={end}
          step={5}
          value={sliderValue}
          onChange={(e) => setAsOf(Number(e.target.value))}
          className="mt-2 w-full accent-brand-600"
        />
        <div className="flex justify-between text-[10px] text-muted">
          <span>{clock(start)}</span>
          <span>{clock(end)}</span>
        </div>
      </div>

      {/* Fleet summary */}
      {fleet ? (
        <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
          <Chip label="Active" value={fleet.active} tone="text-blue-600" />
          <Chip label="At stop" value={fleet.at_stop} tone="text-emerald-600" />
          <Chip label="Returning" value={fleet.returning} tone="text-violet-600" />
          <Chip label="Reloading" value={fleet.reloading} tone="text-amber-600" />
          <Chip label="Done" value={fleet.completed} tone="text-slate-500" />
          <Chip
            label="Late risk"
            value={fleet.predicted_late_stops}
            tone={fleet.predicted_late_stops ? 'text-red-600' : 'text-emerald-600'}
          />
        </div>
      ) : null}

      <div className="mt-3 flex items-center gap-2 text-xs text-muted">
        <Gauge size={13} />
        <span>{fleet ? `${fleet.stops_done}/${fleet.stops_total} stops delivered` : '—'}</span>
        {loading ? <Loader2 size={13} className="ml-1 animate-spin" /> : null}
      </div>

      {error ? <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}

      {/* Truck filter chips — focus one truck's route (syncs with the timeline). */}
      {routeChips.length ? (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {routeChips.map((r) => {
            const on = String(r.truck_id) === String(selectedTruckId);
            return (
              <button
                key={r.truck_id}
                type="button"
                onClick={() => onSelectTruck?.(on ? null : r.truck_id)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition ${
                  on ? 'border-brand-600 bg-brand-600/10 text-brand-600' : 'border-border text-ink hover:bg-canvas'
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: r.color }} />
                {r.truck_label}
                <span className="text-[#9e9aa4]">· {r.stops}</span>
              </button>
            );
          })}
          {selectedTruckId != null ? (
            <button
              type="button"
              onClick={() => onSelectTruck?.(null)}
              className="rounded-full border border-border px-3 py-1 text-xs font-semibold text-muted transition hover:bg-canvas"
            >
              Show all trucks
            </button>
          ) : null}
        </div>
      ) : null}

      {/* Map — planned routes (real roads) + live truck positions in one view. */}
      <div className="mt-4">
        <ControlTowerMap
          plan={plan}
          snapshot={snapshot}
          selectedTruckId={selectedTruckId}
          onSelectTruck={onSelectTruck}
        />
      </div>

      {/* Delay injection */}
      <div className="mt-5">
        <div className="flex items-center justify-between">
          <h3 className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink">
            <Zap size={15} className="text-amber-500" /> Inject a delay
          </h3>
          {Object.values(delays).some((m) => Number(m) > 0) ? (
            <button
              type="button"
              onClick={() => setDelays({})}
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink"
            >
              <RotateCcw size={13} /> Clear
            </button>
          ) : null}
        </div>
        <p className="mt-1 text-xs text-muted">Push a truck behind schedule and watch its at-risk drops light up red.</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {activeTrucks.map((t) => {
            const d = Number(delays[t.truck_id]) || 0;
            return (
              <button
                key={t.truck_id}
                type="button"
                onClick={() => bumpDelay(t.truck_id, 15)}
                title="Click to add 15 minutes of delay"
                className={`rounded-xl border px-3 py-1.5 text-sm font-medium transition ${
                  d ? 'border-amber-500 bg-amber-50 text-amber-700' : 'border-border bg-surface text-ink hover:border-amber-300'
                }`}
              >
                {t.truck_label}{d ? ` +${d}m` : ''}
              </button>
            );
          })}
        </div>
      </div>

      {/* Alerts */}
      {snapshot?.alerts?.length ? (
        <div className="mt-5">
          <h3 className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink">
            <AlertTriangle size={15} className="text-red-500" /> Predicted-late alerts ({snapshot.alerts.length})
          </h3>
          <div className="mt-2 space-y-1.5">
            {snapshot.alerts.slice(0, 8).map((a, i) => (
              <div
                key={`${a.truck_id}-${i}`}
                className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm ${
                  a.severity === 'high' ? 'bg-red-50 text-red-800' : 'bg-amber-50 text-amber-800'
                }`}
              >
                <span className="min-w-0 truncate">
                  <span className="font-semibold">{a.client}</span>
                  <span className="text-xs"> · {a.truck_label}</span>
                </span>
                <span className="ml-3 shrink-0 tabular-nums text-xs">
                  ETA {a.projected_arrival} · window ≤ {a.window_end} ·{' '}
                  <span className="font-semibold">{a.minutes_late}m late</span>
                </span>
              </div>
            ))}
            {snapshot.alerts.length > 8 ? (
              <p className="text-xs text-muted">…and {snapshot.alerts.length - 8} more.</p>
            ) : null}
          </div>
        </div>
      ) : snapshot ? (
        <p className="mt-5 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          ✓ Every stop is currently projected to arrive within its delivery window.
        </p>
      ) : null}

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-3 text-[11px] text-muted">
        {[
          ['en_route', 'En route'],
          ['at_stop', 'At stop'],
          ['returning', 'Returning'],
          ['reloading', 'Reloading'],
          ['completed', 'Done'],
        ].map(([k, label]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: STATE_COLOR[k] }} />
            {label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-red-600" /> Late risk
        </span>
      </div>
    </section>
  );
}

function Header() {
  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-sky-100 text-sky-600">
        <Radio size={18} />
      </span>
      <div>
        <h2 className="text-lg font-semibold text-ink">Routes &amp; Live Control Tower</h2>
        <p className="text-xs text-muted">
          Today’s routes on the map — scrub the day forward to see where every truck is and which drops are about to miss their window.
        </p>
      </div>
    </div>
  );
}

function Chip({ label, value, tone = 'text-ink' }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-2.5 text-center">
      <p className={`text-lg font-semibold tabular-nums ${tone}`}>{value ?? '—'}</p>
      <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>
    </div>
  );
}
