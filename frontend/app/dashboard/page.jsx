"use client";

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Truck,
  Route,
  AlertTriangle,
  BarChart3,
  ChevronRight,
  Boxes,
  Bell,
  Clock,
  Gauge,
  Scale,
  RefreshCcw,
  CalendarClock,
  CalendarDays,
  CalendarRange,
} from 'lucide-react';
import {
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  ComposedChart,
} from 'recharts';
import StatusBadge from '../../components/shared/StatusBadge';
import SustainabilityPanel from '../../components/planning/SustainabilityPanel';
import { generateDailyPlan } from '../services/api';
import { useDailyDashboard } from '../../hooks/useDailyDashboard';
import { useFleet } from '../../hooks/useFleet';
import { trucks as fallbackTrucks } from '../../data/coficabData';
import { applyTruckStatusOverrides, normalizeTruckStatus, UNAVAILABLE_TRUCK_STATUSES } from '../../utils/truckStatus';
import { palette } from '@/lib/theme';

const TruckMapPreview = dynamic(() => import('../../components/map/TruckMap'), { ssr: false });

const iconMap = {
  truck: Truck,
  route: Route,
  clock: Clock,
  gauge: Gauge,
  weight: Scale,
  'alert-triangle': AlertTriangle,
  'bar-chart-3': BarChart3,
};

const alertIconMap = {
  'alert-triangle': AlertTriangle,
  clock: Clock,
  info: Bell,
};

// Accent colour per official KPI, and the traffic-light band → hex.
const KPI_ACCENT = {
  otif: { bg: 'rgba(124,58,237,0.1)', color: palette.brand[600] },
  otd: { bg: 'rgba(59,130,246,0.1)', color: '#3b82f6' },
  load: { bg: 'rgba(20,184,166,0.1)', color: '#14b8a6' },
  weight: { bg: 'rgba(249,115,22,0.1)', color: '#f97316' },
  premium_cost: { bg: 'rgba(249,115,22,0.1)', color: '#f97316' },
  premium_occ: { bg: 'rgba(239,68,68,0.1)', color: '#ef4444' },
  fuel: { bg: 'rgba(20,184,166,0.1)', color: '#14b8a6' },
  logistics_cost: { bg: 'rgba(59,130,246,0.1)', color: '#3b82f6' },
  incidents: { bg: 'rgba(245,158,11,0.1)', color: '#f59e0b' },
};
const BAND_COLOR = { green: '#22c55e', yellow: '#f59e0b', red: '#ef4444', grey: '#9e9ea4' };
const BAND_LABEL = { green: 'on target', yellow: 'watch', red: 'below target', grey: 'no data' };
const KPI_PLACEHOLDERS = [{ id: 'otif' }, { id: 'load' }, { id: 'otd' }, { id: 'fuel' }];
const PERIOD_OPTIONS = [
  { id: 'daily', label: 'Daily', icon: CalendarClock },
  { id: 'weekly', label: 'Weekly', icon: CalendarDays },
  { id: 'monthly', label: 'Monthly', icon: CalendarRange },
];

// Map backend trip status → StatusBadge / timeline colours.
const STATUS_MAP = {
  completed: 'completed',
  in_transit: 'in-transit',
  pending: 'scheduled',
};

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

// Map a fleet row → the backend's daily-plan truck payload, dropping trucks that
// are unavailable (broken down / maintenance). Mirrors the generated-planning
// screen so the dashboard plans with the SAME active fleet.
function toDailyTruckPayload(truck) {
  const status = normalizeTruckStatus(truck.status);
  if (UNAVAILABLE_TRUCK_STATUSES.has(status)) return null;
  const capacityPositions = Number(truck.capacity_positions ?? truck.max_palettes ?? truck.max_pallets ?? 0);
  const capacityKg = Number(truck.capacity_kg ?? truck.capacite_kg ?? truck.capacity ?? 0);
  if (!capacityPositions) return null;
  return {
    truck_id: truck.id ?? truck.truck_id,
    truck_label: truck.plate_number || truck.truck_label || `Truck ${truck.id ?? truck.truck_id}`,
    capacity_positions: capacityPositions,
    capacity_kg: capacityKg,
  };
}

function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-3 border border-border text-sm">
        <p className="font-semibold text-ink mb-1">{label}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-muted">{entry.name}:</span>
            <span className="font-semibold text-ink">{entry.value} pos</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export default function DashboardPage() {
  const [period, setPeriod] = useState('weekly');
  const { trucks: apiTrucks } = useFleet();
  // The active fleet (trucks not marked unavailable), so the dashboard plans with
  // the same trucks as the planning screen and agrees on what goes unassigned.
  const activeTrucks = useMemo(() => (
    applyTruckStatusOverrides((apiTrucks && apiTrucks.length ? apiTrucks : fallbackTrucks))
      .map(toDailyTruckPayload)
      .filter(Boolean)
  ), [apiTrucks]);
  const { dashboard, isLoading, mutate } = useDailyDashboard(undefined, period, activeTrucks);
  const [plan, setPlan] = useState(null);

  // Pull the same day's real plan the dashboard metrics were derived from, so
  // the Live Route Map preview plots actual client stops (not the static
  // directory). The plan carries no live truck GPS, so only stops are mapped.
  useEffect(() => {
    if (!dashboard?.day) return;
    let cancelled = false;
    generateDailyPlan(dashboard.day)
      .then((p) => { if (!cancelled) setPlan(p); })
      .catch(() => { /* preview stays empty if the plan can't be built */ });
    return () => { cancelled = true; };
  }, [dashboard?.day]);

  const mapClients = useMemo(() => {
    if (!plan) return [];
    const stops = (plan.trucks || []).flatMap((t) =>
      (t.trips || []).flatMap((tr) => tr.stops || []),
    );
    return [...stops, ...(plan.unassigned || [])].map((s, i) => ({
      id: s.id ?? `stop-${i}`,
      customer: s.client,
      destination: s.resolved_location || s.end_location || s.client,
      km: s.distance_km,
      lat: s.lat,
      lng: s.lng,
    }));
  }, [plan]);

  const kpis = dashboard?.kpis ?? [];
  const totals = dashboard?.totals ?? {};
  const fleet = dashboard?.fleet ?? [];
  const efficiency = dashboard?.efficiency ?? [];
  const activity = dashboard?.activity ?? [];
  const alerts = dashboard?.alerts ?? [];
  const weeklyData = dashboard?.weekly ?? [];

  const planDate = dashboard?.day
    ? new Date(`${dashboard.day}T00:00:00`).toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
    : '…';

  return (
    <div className="p-8 min-h-screen bg-canvas">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between mb-8"
      >
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-brand-600">Operations dashboard</p>
          <h1 className="mt-3 text-4xl font-bold text-ink">{greeting()}, Ghada</h1>
          <p className="mt-2 text-sm text-muted">
            {planDate} · Live from {dashboard?.source_file || 'the weekly planning'} — fleet, routes and delivery performance.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => mutate()}
            className="inline-flex items-center gap-2 rounded-2xl border border-border bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-canvas transition"
          >
            <RefreshCcw size={16} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <Link
            href="/generated-daily-planning"
            className="inline-flex items-center gap-2 rounded-2xl bg-brand-600 px-5 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition shadow-sm"
          >
            <Route size={16} />
            Open planning
          </Link>
        </div>
      </motion.div>

      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Performance KPIs</h2>
          {dashboard?.kpi_period && (
            <p className="mt-1 text-xs text-muted">
              {dashboard.kpi_period.label} · {dashboard.kpi_period.days} day(s) of travel
              {isLoading && <span className="text-[#c4c2bd]"> · updating…</span>}
            </p>
          )}
        </div>

        {/* Period switcher: pick the daily / weekly / monthly KPI view. */}
        <div
          role="group"
          aria-label="KPI period"
          className="inline-flex items-center gap-1 rounded-2xl border border-border bg-white p-1 shadow-sm"
        >
          {PERIOD_OPTIONS.map(({ id, label, icon: Icon }) => {
            const active = period === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setPeriod(id)}
                aria-pressed={active}
                title={`${label} KPIs`}
                className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition ${
                  active ? 'bg-brand-600 text-white shadow-sm' : 'text-muted hover:bg-canvas hover:text-ink'
                }`}
              >
                <Icon size={16} />
                <span className="hidden sm:inline">{label}</span>
              </button>
            );
          })}
        </div>
      </div>
      <motion.div variants={container} initial="hidden" animate="show" className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
        {(kpis.length ? kpis : KPI_PLACEHOLDERS).map((kpi) => {
          const accent = KPI_ACCENT[kpi.id] || KPI_ACCENT.otif;
          const Icon = iconMap[kpi.icon] || BarChart3;
          const band = BAND_COLOR[kpi.color] || BAND_COLOR.grey;
          const hasValue = kpi.value !== null && kpi.value !== undefined;
          const display = hasValue ? `${kpi.value}${kpi.unit === '%' ? '%' : ''}` : '—';
          const unitSuffix = kpi.unit && kpi.unit !== '%' ? kpi.unit : '';
          return (
            <motion.div
              key={kpi.id}
              variants={item}
              whileHover={{ y: -3, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
              className="bg-white rounded-2xl p-6 border border-border cursor-pointer transition-shadow"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: accent.bg }}>
                  <Icon size={20} color={accent.color} />
                </div>
                {hasValue && (
                  <span
                    className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold"
                    style={{ backgroundColor: `${band}1a`, color: band }}
                  >
                    <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: band }} />
                    {BAND_LABEL[kpi.color] || ''}
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-muted">{kpi.label || '…'}</p>
                {kpi.code && <span className="text-[10px] font-semibold text-[#c4c2bd]">{kpi.code}</span>}
              </div>
              <p className="mt-1 text-4xl font-bold text-ink">
                {display}
                {unitSuffix && <span className="ml-1 text-base font-semibold text-[#9e9ea4]">{unitSuffix}</span>}
              </p>
              <p className="mt-2 text-xs text-[#9e9ea4]">
                {hasValue && kpi.target != null ? `Target ${kpi.target}${kpi.unit === '%' ? '%' : ` ${kpi.unit}`} · ` : ''}
                {kpi.hint || 'planned from today’s schedule'}
              </p>
            </motion.div>
          );
        })}
      </motion.div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6 mb-8">
        <div className="xl:col-span-3 space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="bg-white rounded-2xl p-6 border border-border"
          >
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-base font-semibold text-ink">Weekly Delivery Analytics</h3>
                <p className="text-sm text-muted">Delivered vs. planned positions (Mon–Sun)</p>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={weeklyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0ede8" vertical={false} />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#9e9ea4', fontSize: 12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9e9ea4', fontSize: 12 }} domain={[0, 'auto']} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="delivered" fill={palette.brand[600]} radius={[4, 4, 0, 0]} name="Delivered" barSize={28} />
                  <Line type="monotone" dataKey="planned" stroke="#f97316" strokeWidth={2.5} dot={{ r: 4, fill: '#f97316', strokeWidth: 0 }} name="Planned" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center gap-6 mt-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-brand-600" />
                <span className="text-sm text-muted">Delivered</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[#f97316]" />
                <span className="text-sm text-muted">Planned (demand)</span>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-border"
          >
            <div className="mb-6 flex items-center justify-between">
              <div>
                <p className="text-sm text-muted">Fleet health</p>
                <h2 className="text-2xl font-semibold text-ink">Vehicle utilization</h2>
              </div>
              <Link href="/vehicles" className="text-sm font-semibold text-brand-600 hover:text-brand-800">View fleet</Link>
            </div>
            <div className="space-y-4">
              {fleet.length === 0 && (
                <p className="text-sm text-[#9e9ea4]">{isLoading ? 'Loading plan…' : 'No trucks dispatched for this day.'}</p>
              )}
              {fleet.map((vehicle) => {
                const fillColor = vehicle.utilization >= 90 ? '#22c55e' : vehicle.utilization >= 80 ? '#f59e0b' : '#ef4444';
                return (
                  <div key={vehicle.name} className="space-y-2">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="font-semibold text-ink">{vehicle.name}</p>
                        <p className="text-sm text-muted mt-1">
                          {vehicle.type} · {vehicle.trips} trip(s) · {vehicle.positions}/{vehicle.capacity} pos
                        </p>
                      </div>
                      <p className="text-sm font-semibold" style={{ color: fillColor }}>{vehicle.utilization}%</p>
                    </div>
                    <div className="h-2 rounded-full bg-[#f0ede8] overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(100, vehicle.utilization)}%`, backgroundColor: fillColor }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-border"
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-base font-semibold text-ink">Recent Route Activity</h3>
              <Link href="/generated-daily-planning" className="text-sm text-brand-600 font-medium hover:underline">
                View All <ChevronRight size={14} className="inline" />
              </Link>
            </div>
            <div className="space-y-4">
              {activity.length === 0 && (
                <p className="text-sm text-[#9e9ea4]">{isLoading ? 'Loading trips…' : 'No trips for this day.'}</p>
              )}
              {activity.map((event, index) => {
                const mapped = STATUS_MAP[event.status] || 'scheduled';
                return (
                  <motion.div
                    key={event.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.03 + 0.2 }}
                    className="flex gap-4 relative"
                  >
                    {index < activity.length - 1 && (
                      <div className="absolute left-[7px] top-6 w-0.5 h-full bg-border" />
                    )}
                    <div className="flex flex-col items-center">
                      <div
                        className="w-4 h-4 rounded-full border-2 flex-shrink-0 mt-1"
                        style={{
                          backgroundColor: mapped === 'completed' ? '#22c55e' : mapped === 'in-transit' ? '#3b82f6' : palette.brand[600],
                          borderColor: mapped === 'completed' ? '#dcfce7' : mapped === 'in-transit' ? '#dbeafe' : '#f5f3ff',
                        }}
                      />
                    </div>
                    <div className="flex-1 pb-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <span className="text-sm font-semibold text-ink">{event.route}</span>
                          <p className="text-sm text-muted mt-0.5">{event.description}</p>
                          <p className="text-xs text-[#9e9aa4] mt-1">{event.time}</p>
                        </div>
                        <StatusBadge status={mapped} size="sm" />
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        </div>

        <div className="xl:col-span-2 space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-border"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-ink">Route Efficiency</h3>
              <span className="text-xs text-[#9e9aa4]">by trip fill</span>
            </div>
            <div className="flex flex-col items-center">
              <div className="relative w-48 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={efficiency.length ? efficiency : [{ name: 'n/a', value: 100, color: palette.border }]}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                      startAngle={90}
                      endAngle={-270}
                    >
                      {(efficiency.length ? efficiency : [{ color: palette.border }]).map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-ink">{dashboard ? `${dashboard.efficiency_score}%` : '—'}</span>
                  <span className="text-xs text-[#9e9aa4]">Avg. fill</span>
                </div>
              </div>
              <div className="flex items-center gap-4 mt-4 flex-wrap justify-center">
                {efficiency.map((seg) => (
                  <div key={seg.name} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: seg.color }} />
                    <span className="text-xs text-muted">{seg.name} {seg.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl border border-border overflow-hidden"
          >
            <div className="flex items-center justify-between p-5 pb-3">
              <h3 className="text-base font-semibold text-ink">Live Route Map</h3>
              <span className="flex items-center gap-1.5 text-xs">
                <span className="w-2 h-2 rounded-full bg-[#22c55e]" />
                <span className="text-muted">{formatNumber(totals.active_trucks)} Active</span>
              </span>
            </div>
            <div className="px-5 pb-5">
              <TruckMapPreview
                trucks={[]}
                clients={mapClients}
                height={220}
                hideHeader
              />
            </div>
            <div className="px-5 pb-5 flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-1.5 text-xs text-muted">
                <span className="w-2 h-2 rounded-full bg-brand-600" /> Optimized
              </div>
              <div className="flex items-center gap-1.5 text-xs text-muted">
                <span className="w-2 h-2 rounded-full bg-[#f97316]" /> Standard
              </div>
              <Link href="/map" className="ml-auto text-xs text-brand-600 font-medium hover:underline">
                View Full Map →
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-border"
          >
            <h3 className="text-base font-semibold text-ink mb-4">Transport today</h3>
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-xl bg-[#14b8a6]/10 flex items-center justify-center mb-3">
                <Boxes size={24} className="text-[#14b8a6]" />
              </div>
              <p className="text-2xl font-bold text-[#14b8a6]">{formatNumber(totals.tonnes)} t</p>
              <p className="text-sm text-muted mb-4">gross weight over {formatNumber(totals.distance_km)} km</p>
              <div className="grid grid-cols-2 gap-3 w-full">
                <div className="rounded-xl bg-canvas p-3">
                  <p className="text-lg font-semibold text-ink">{formatNumber(totals.positions_planned)}</p>
                  <p className="text-xs text-[#9e9aa4]">positions</p>
                </div>
                <div className="rounded-xl bg-canvas p-3">
                  <p className="text-lg font-semibold text-ink">{formatNumber(totals.premium_trips)}</p>
                  <p className="text-xs text-[#9e9aa4]">premium (rented) trips</p>
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-border"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-ink">Planning Alerts</h3>
              <span className="text-xs font-semibold bg-[#f97316] text-white rounded-md px-2 py-0.5">{alerts.length}</span>
            </div>
            <div className="space-y-3">
              {alerts.length === 0 && (
                <p className="text-sm text-[#9e9ea4]">{isLoading ? 'Loading…' : 'No alerts — every delivery is assigned and on target.'}</p>
              )}
              {alerts.map((alert) => {
                const AlertIcon = alertIconMap[alert.icon] || Bell;
                const accent = alert.severity === 'critical' ? '#ef4444' : alert.severity === 'warning' ? '#f59e0b' : '#3b82f6';
                const bg = alert.severity === 'critical' ? '#fef2f2' : alert.severity === 'warning' ? '#fffbeb' : '#eff6ff';
                return (
                  <motion.div
                    key={alert.id}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="p-3 rounded-xl border-l-[3px]"
                    style={{ backgroundColor: bg, borderLeftColor: accent }}
                  >
                    <div className="flex items-start gap-3">
                      <AlertIcon size={18} style={{ color: accent }} className="flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-ink">{alert.title}</p>
                        <p className="text-xs text-muted mt-0.5">{alert.description}</p>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        </div>
      </div>

      {/* Carbon & ESG — derived from the same day's generated plan. */}
      {plan?.sustainability && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="mb-8"
        >
          <SustainabilityPanel
            plan={plan}
            day={dashboard?.day}
            activeTrucks={activeTrucks}
            onApplyPlan={setPlan}
          />
        </motion.div>
      )}
    </div>
  );
}
