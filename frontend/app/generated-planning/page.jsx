"use client";

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertCircle,
  CalendarDays,
  CheckCircle,
  Clock,
  MapPin,
  Package,
  RefreshCcw,
  Sparkles,
  TrendingDown,
  Truck,
} from 'lucide-react';
import { getClientPosition, trucks as fallbackTrucks } from '../../data/coficabData';
import { useFleet } from '../../hooks/useFleet';
import { applyTruckStatusOverrides, normalizeTruckStatus, UNAVAILABLE_TRUCK_STATUSES } from '../../utils/truckStatus';
import { generatePlanning, getDailyPlanningFileResponse } from '../services/api';

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function formatTime(minutes) {
  if (!Number.isFinite(Number(minutes))) return '--:--';
  const safe = Math.max(0, Math.min(Number(minutes), 23 * 60 + 59));
  const h = Math.floor(safe / 60);
  const m = safe % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

function parseTimeToMinutes(value) {
  if (!value) return null;
  const cleaned = String(value).trim();
  const parts = cleaned.split(':').map((part) => Number(part));
  if (parts.length >= 2 && parts.every((part) => Number.isFinite(part))) {
    return parts[0] * 60 + parts[1];
  }
  const numeric = Number(cleaned);
  if (Number.isFinite(numeric) && numeric >= 0 && numeric < 2400) {
    const hours = Math.floor(numeric / 100);
    const minutes = numeric % 100;
    return hours * 60 + minutes;
  }
  return null;
}

function money(value) {
  return `${Number(value || 0).toFixed(2)} EUR`;
}

function normalizeSuggestion(suggestion) {
  if (typeof suggestion === 'string') {
    return { severity: 'info', message: suggestion, action: 'Review the generated route.' };
  }
  return {
    severity: suggestion?.severity || 'info',
    message: suggestion?.message || 'Planning recommendation',
    action: suggestion?.action || 'Review this item before dispatch.',
  };
}

function totalPositions(plan) {
  return (plan?.routes || []).reduce((sum, route) => (
    sum + Number(route.load || route.stops?.reduce((stopSum, stop) => stopSum + Number(stop.quantity || 0), 0) || 0)
  ), 0);
}

function emptyPlan() {
  return {
    status: 'empty',
    algorithm: 'No deliveries',
    routes: [],
    unassigned: [],
    costs: { before: 0, after: 0, savings: 0, savings_percent: 0 },
    suggestions: [],
    metrics: { total_routes: 0, total_deliveries: 0, total_distance: 0, avg_utilization_percent: 0 },
  };
}

export default function GeneratedPlanningPage() {
  const { trucks: fleetTrucks } = useFleet();
  const [plan, setPlan] = useState(null);
  const [rows, setRows] = useState([]);
  const [days, setDays] = useState([]);
  const [selectedDay, setSelectedDay] = useState('');
  const [sourceMeta, setSourceMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedRoute, setExpandedRoute] = useState(0);

  const sourceLabel = sourceMeta?.file_name || sourceMeta?.source_file || 'weekly planning workbook';

  const activeTrucks = useMemo(() => (
    applyTruckStatusOverrides(fleetTrucks.length ? fleetTrucks : fallbackTrucks)
      .filter((truck) => {
        const status = normalizeTruckStatus(truck.status);
        return !UNAVAILABLE_TRUCK_STATUSES.has(status);
      })
      .map((truck) => ({
        id: truck.id,
        type: truck.type,
        capacity: Number.isFinite(Number(truck.max_palettes ?? truck.max_pallets))
          ? Number(truck.max_palettes ?? truck.max_pallets)
          : Number(truck.capacity ?? 33),
      }))
  ), [fleetTrucks]);

  async function buildPlan(sourceRows, day) {
    setLoading(true);
    setError(null);
    try {
      const dayRows = sourceRows
        .filter((row) => !day || row.delivery_day === day)
        .filter((row) => row.client && row.status !== 'completed');

      if (dayRows.length === 0) {
        setPlan(emptyPlan());
        return;
      }

      const deliveries = dayRows.map((row, index) => {
        const [lat, lng] = getClientPosition(row.end_location || row.client, index);
        const earliest = parseTimeToMinutes(row.etd) ?? 480;
        const latest = parseTimeToMinutes(row.eta) ?? Math.min(1020, earliest + 180);
        const quantity = Math.max(1, Number(row.position_count ?? row.quantity ?? 1));
        return {
          id: Number(row.row_number || row.id || index + 1),
          row_number: row.row_number,
          customer: row.client,
          quantity,
          delivery_day: row.delivery_day,
          lat,
          lng,
          earliest_time: earliest,
          latest_time: Math.max(latest, earliest + 15),
        };
      });

      const result = await generatePlanning({ deliveries, trucks: activeTrucks });
      setPlan(result);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to generate planning from the workbook.');
      setPlan(emptyPlan());
    } finally {
      setLoading(false);
    }
  }

  async function loadWorkbook() {
    setLoading(true);
    setError(null);
    try {
      const response = await getDailyPlanningFileResponse();
      const extractedRows = (response.transports || []).filter((row) => row.client);
      const workbookDays = [...new Set(extractedRows.map((row) => row.delivery_day).filter(Boolean))];
      const initialDay = selectedDay || workbookDays[0] || '';
      setRows(extractedRows);
      setDays(workbookDays);
      setSelectedDay(initialDay);
      setSourceMeta(response);
      await buildPlan(extractedRows, initialDay);
      if (response.used_mock) {
        setError(response.error || 'Workbook data was unavailable, so mock data was used.');
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to read the weekly planning workbook.');
      setPlan(emptyPlan());
      setLoading(false);
    }
  }

  useEffect(() => {
    loadWorkbook();
  }, []);

  function handleDayChange(day) {
    setSelectedDay(day);
    buildPlan(rows, day);
  }

  if (loading && !plan) {
    return (
      <div className="min-h-screen bg-[#f8f7f3] p-8">
        <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-8 shadow-sm">
          <div className="h-64 rounded-2xl bg-[#f0eee9] animate-pulse" />
        </div>
      </div>
    );
  }

  const suggestions = (plan?.suggestions || []).map(normalizeSuggestion);
  const metrics = plan?.metrics || {};
  const costs = plan?.costs || {};

  return (
    <div className="min-h-screen bg-[#f8f7f3] p-8">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-8 flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">AI VRPTW Optimizer</p>
          <h1 className="mt-3 text-3xl font-semibold text-[#1a1a2e]">Generated Planning</h1>
          <p className="mt-2 text-sm text-[#6b6b7b]">
            Extracted from {sourceLabel}{selectedDay ? ` for ${selectedDay}` : ''}.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-4 py-2 text-sm font-semibold text-[#1a1a2e]">
            <CalendarDays size={16} />
            <select
              value={selectedDay}
              onChange={(event) => handleDayChange(event.target.value)}
              className="bg-transparent outline-none"
            >
              {days.map((day) => <option key={day} value={day}>{day}</option>)}
            </select>
          </label>
          <button
            type="button"
            onClick={loadWorkbook}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-full border border-[#e8e5df] bg-white px-5 py-2 text-sm font-semibold text-[#1a1a2e] transition hover:bg-[#faf8f5] disabled:opacity-60"
          >
            <RefreshCcw size={16} />
            Refresh
          </button>
        </div>
      </motion.div>

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <motion.div variants={container} initial="hidden" animate="show" className="mb-8 grid gap-6 sm:grid-cols-2 xl:grid-cols-6">
        {[
          ['Routes', metrics.total_routes, Truck],
          ['Stops', metrics.total_deliveries, MapPin],
          ['Distance', `${Number(metrics.total_distance || 0).toFixed(0)} km`, Clock],
          ['Utilization', `${Number(metrics.avg_utilization_percent || 0).toFixed(0)}%`, CheckCircle],
          ['Savings', `${Number(costs.savings_percent || 0).toFixed(0)}%`, TrendingDown],
          ['Positions', totalPositions(plan), Package],
        ].map(([label, value, Icon]) => (
          <motion.div key={label} variants={item} className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-3 inline-flex rounded-2xl bg-[#7c3aed]/10 p-3 text-[#7c3aed]"><Icon size={18} /></div>
            <p className="text-xs uppercase tracking-[0.18em] text-[#6b6b7b]">{label}</p>
            <p className="mt-2 text-3xl font-semibold text-[#1a1a2e]">{loading ? '--' : value}</p>
          </motion.div>
        ))}
      </motion.div>

      <div className="mb-8 rounded-[1.75rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-[#1a1a2e]">Cost comparison</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <p className="mb-2 text-sm text-[#6b6b7b]">Before optimization</p>
            <p className="text-3xl font-semibold text-red-600">{money(costs.before)}</p>
          </div>
          <div className="flex items-center justify-center">
            <div className="text-center">
              <TrendingDown size={30} className="mx-auto mb-2 text-emerald-500" />
              <p className="text-sm font-semibold text-emerald-600">{Number(costs.savings_percent || 0).toFixed(1)}%</p>
            </div>
          </div>
          <div>
            <p className="mb-2 text-sm text-[#6b6b7b]">After optimization</p>
            <p className="text-3xl font-semibold text-emerald-600">{money(costs.after)}</p>
          </div>
        </div>
      </div>

      {(plan?.unassigned || []).length > 0 && (
        <div className="mb-8 rounded-[1.75rem] border border-red-200 bg-red-50 p-5">
          <div className="mb-3 flex items-center gap-2 text-red-700">
            <AlertCircle size={16} />
            <h2 className="text-sm font-semibold uppercase tracking-[0.18em]">Unassigned deliveries</h2>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {plan.unassigned.map((delivery) => (
              <div key={`${delivery.delivery_day}-${delivery.id}`} className="rounded-2xl border border-red-200 bg-white p-4">
                <p className="font-semibold text-[#1a1a2e]">{delivery.customer || `Row ${delivery.id}`}</p>
                <p className="mt-1 text-xs text-[#6b6b7b]">{delivery.quantity} positions</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-6">
        {(plan?.routes || []).map((route, routeIdx) => (
          <motion.div
            key={`${route.truck_id}-${route.trip_number || routeIdx}`}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: routeIdx * 0.05 }}
            className="overflow-hidden rounded-[1.75rem] border border-[#e8e5df] bg-white shadow-sm"
          >
            <button
              type="button"
              onClick={() => setExpandedRoute(expandedRoute === routeIdx ? -1 : routeIdx)}
              className="flex w-full items-center justify-between gap-4 border-b border-[#e8e5df] bg-[#f8f7f3] p-6 text-left transition hover:bg-[#f0eee9]"
            >
              <div className="flex min-w-0 items-center gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#7c3aed] font-semibold text-white">
                  {routeIdx + 1}
                </div>
                <div className="min-w-0">
                  <h3 className="truncate font-semibold text-[#1a1a2e]">{route.truck_id}</h3>
                  <p className="mt-1 text-sm text-[#6b6b7b]">
                    {formatTime(route.start_time)} - {formatTime(route.end_time)} - {route.stops?.length || 0} stops - {Number(route.total_distance || 0).toFixed(1)} km
                  </p>
                  <p className="mt-1 text-xs text-[#6b6b7b]">
                    Capacity {route.capacity ?? 'N/A'} positions - Load {route.load ?? 0} positions
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-semibold text-[#1a1a2e]">{money(route.total_cost)}</p>
                <p className="text-xs text-[#6b6b7b]">Route cost</p>
              </div>
            </button>

            {expandedRoute === routeIdx && (
              <div className="space-y-4 p-6">
                <div className="flex gap-4">
                  <div className="w-20 text-right font-semibold text-[#7c3aed]">{formatTime(route.start_time)}</div>
                  <div className="flex-1 rounded-2xl border border-[#ddd6fe] bg-[#f5f3ff] p-3 font-semibold text-[#4c1d95]">Departure from depot</div>
                </div>

                {(route.stops || []).map((stop) => (
                  <div key={`${route.truck_id}-${stop.client_id}-${stop.arrival_time}`} className="flex gap-4">
                    <div className="w-20 text-right">
                      <p className="font-semibold text-[#1a1a2e]">{formatTime(stop.arrival_time)}</p>
                      <p className="text-xs text-[#6b6b7b]">{formatTime(stop.departure_time)}</p>
                    </div>
                    <div className={`flex-1 rounded-2xl border p-4 ${
                      stop.status === 'OK' ? 'border-emerald-200 bg-emerald-50' :
                      stop.status === 'EARLY' ? 'border-amber-200 bg-amber-50' :
                      'border-red-200 bg-red-50'
                    }`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-[#1a1a2e]">{stop.client_name}</p>
                          <p className="mt-1 text-xs text-[#6b6b7b]">Row {stop.client_id} - {stop.quantity || 0} positions</p>
                        </div>
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[#1a1a2e]">{stop.status}</span>
                      </div>
                    </div>
                  </div>
                ))}

                <div className="flex gap-4">
                  <div className="w-20 text-right font-semibold text-[#7c3aed]">{formatTime(route.end_time)}</div>
                  <div className="flex-1 rounded-2xl border border-[#ddd6fe] bg-[#f5f3ff] p-3 font-semibold text-[#4c1d95]">Return to depot</div>
                </div>
              </div>
            )}
          </motion.div>
        ))}

        {(plan?.routes || []).length === 0 && (
          <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-8 text-sm text-[#6b6b7b] shadow-sm">
            No route was generated for the selected day.
          </div>
        )}
      </div>

      {suggestions.length > 0 && (
        <div className="mt-8 rounded-[1.75rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-[#1a1a2e]">Recommendations</h2>
          <div className="space-y-3">
            {suggestions.map((suggestion, idx) => (
              <div key={`${suggestion.message}-${idx}`} className="rounded-2xl border border-[#e8e5df] bg-[#f8f7f3] p-4">
                <div className="flex gap-3">
                  <AlertCircle size={18} className={suggestion.severity === 'high' ? 'text-red-500' : suggestion.severity === 'warning' ? 'text-amber-500' : 'text-blue-500'} />
                  <div>
                    <p className="font-semibold text-[#1a1a2e]">{suggestion.message}</p>
                    <p className="mt-1 text-sm text-[#6b6b7b]">{suggestion.action}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
