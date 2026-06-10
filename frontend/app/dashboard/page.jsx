"use client";

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
import { clients as initialClients, getClientPosition } from '../../data/coficabData';
import { useDailyDashboard } from '../../hooks/useDailyDashboard';

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
  otif: { bg: 'rgba(124,58,237,0.1)', color: '#7c3aed' },
  otd: { bg: 'rgba(59,130,246,0.1)', color: '#3b82f6' },
  load: { bg: 'rgba(20,184,166,0.1)', color: '#14b8a6' },
  weight: { bg: 'rgba(249,115,22,0.1)', color: '#f97316' },
};
const BAND_COLOR = { green: '#22c55e', yellow: '#f59e0b', red: '#ef4444', grey: '#9e9ea4' };
const BAND_LABEL = { green: 'on target', yellow: 'watch', red: 'below target', grey: 'no data' };
const KPI_PLACEHOLDERS = [{ id: 'otif' }, { id: 'otd' }, { id: 'load' }, { id: 'weight' }];

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

function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-3 border border-[#e8e5df] text-sm">
        <p className="font-semibold text-[#1a1a2e] mb-1">{label}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-[#6b6b7b]">{entry.name}:</span>
            <span className="font-semibold text-[#1a1a2e]">{entry.value} pos</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export default function DashboardPage() {
  const { dashboard, isLoading, mutate } = useDailyDashboard();

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
    <div className="p-8 min-h-screen bg-[#f8f7f3]">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between mb-8"
      >
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Operations dashboard</p>
          <h1 className="mt-3 text-4xl font-bold text-[#1a1a2e]">{greeting()}, Ghada</h1>
          <p className="mt-2 text-sm text-[#6b6b7b]">
            {planDate} · Live from {dashboard?.source_file || 'the weekly planning'} — fleet, routes and delivery performance.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => mutate()}
            className="inline-flex items-center gap-2 rounded-2xl border border-[#e8e5df] bg-white px-4 py-2 text-sm font-semibold text-[#1a1a2e] hover:bg-[#faf8f5] transition"
          >
            <RefreshCcw size={16} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <Link
            href="/generated-daily-planning"
            className="inline-flex items-center gap-2 rounded-2xl bg-[#7c3aed] px-5 py-2 text-sm font-semibold text-white hover:bg-[#6d28d9] transition shadow-sm"
          >
            <Route size={16} />
            Open planning
          </Link>
        </div>
      </motion.div>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-[#1a1a2e]">Performance KPIs</h2>
        {dashboard?.kpi_period && (
          <span className="text-xs text-[#6b6b7b]">
            Average over {dashboard.kpi_period.days} day(s) · {dashboard.kpi_period.month}
            <span className="text-[#c4c2bd]"> ({dashboard.kpi_period.range})</span>
          </span>
        )}
      </div>
      <motion.div variants={container} initial="hidden" animate="show" className="grid gap-6 xl:grid-cols-4 mb-8">
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
              className="bg-white rounded-2xl p-6 border border-[#e8e5df] cursor-pointer transition-shadow"
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
                <p className="text-sm font-medium text-[#6b6b7b]">{kpi.label || '…'}</p>
                {kpi.code && <span className="text-[10px] font-semibold text-[#c4c2bd]">{kpi.code}</span>}
              </div>
              <p className="mt-1 text-4xl font-bold text-[#1a1a2e]">
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

      <div className="grid grid-cols-5 gap-6 mb-8">
        <div className="col-span-3 space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="bg-white rounded-2xl p-6 border border-[#e8e5df]"
          >
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-base font-semibold text-[#1a1a2e]">Weekly Delivery Analytics</h3>
                <p className="text-sm text-[#6b6b7b]">Delivered vs. planned positions (Mon–Sun)</p>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={weeklyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0ede8" vertical={false} />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#9e9ea4', fontSize: 12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9e9ea4', fontSize: 12 }} domain={[0, 'auto']} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="delivered" fill="#7c3aed" radius={[4, 4, 0, 0]} name="Delivered" barSize={28} />
                  <Line type="monotone" dataKey="planned" stroke="#f97316" strokeWidth={2.5} dot={{ r: 4, fill: '#f97316', strokeWidth: 0 }} name="Planned" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center gap-6 mt-4">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[#7c3aed]" />
                <span className="text-sm text-[#6b6b7b]">Delivered</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-[#f97316]" />
                <span className="text-sm text-[#6b6b7b]">Planned (demand)</span>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-[#e8e5df]"
          >
            <div className="mb-6 flex items-center justify-between">
              <div>
                <p className="text-sm text-[#6b6b7b]">Fleet health</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Vehicle utilization</h2>
              </div>
              <Link href="/vehicles" className="text-sm font-semibold text-[#7c3aed] hover:text-[#5b21b6]">View fleet</Link>
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
                        <p className="font-semibold text-[#1a1a2e]">{vehicle.name}</p>
                        <p className="text-sm text-[#6b6b7b] mt-1">
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
            className="bg-white rounded-2xl p-6 border border-[#e8e5df]"
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-base font-semibold text-[#1a1a2e]">Recent Route Activity</h3>
              <Link href="/generated-daily-planning" className="text-sm text-[#7c3aed] font-medium hover:underline">
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
                      <div className="absolute left-[7px] top-6 w-0.5 h-full bg-[#e8e5df]" />
                    )}
                    <div className="flex flex-col items-center">
                      <div
                        className="w-4 h-4 rounded-full border-2 flex-shrink-0 mt-1"
                        style={{
                          backgroundColor: mapped === 'completed' ? '#22c55e' : mapped === 'in-transit' ? '#3b82f6' : '#7c3aed',
                          borderColor: mapped === 'completed' ? '#dcfce7' : mapped === 'in-transit' ? '#dbeafe' : '#f5f3ff',
                        }}
                      />
                    </div>
                    <div className="flex-1 pb-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <span className="text-sm font-semibold text-[#1a1a2e]">{event.route}</span>
                          <p className="text-sm text-[#6b6b7b] mt-0.5">{event.description}</p>
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

        <div className="col-span-2 space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-[#e8e5df]"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-[#1a1a2e]">Route Efficiency</h3>
              <span className="text-xs text-[#9e9aa4]">by trip fill</span>
            </div>
            <div className="flex flex-col items-center">
              <div className="relative w-48 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={efficiency.length ? efficiency : [{ name: 'n/a', value: 100, color: '#e8e5df' }]}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                      startAngle={90}
                      endAngle={-270}
                    >
                      {(efficiency.length ? efficiency : [{ color: '#e8e5df' }]).map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-[#1a1a2e]">{dashboard ? `${dashboard.efficiency_score}%` : '—'}</span>
                  <span className="text-xs text-[#9e9aa4]">Avg. fill</span>
                </div>
              </div>
              <div className="flex items-center gap-4 mt-4 flex-wrap justify-center">
                {efficiency.map((seg) => (
                  <div key={seg.name} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: seg.color }} />
                    <span className="text-xs text-[#6b6b7b]">{seg.name} {seg.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl border border-[#e8e5df] overflow-hidden"
          >
            <div className="flex items-center justify-between p-5 pb-3">
              <h3 className="text-base font-semibold text-[#1a1a2e]">Live Route Map</h3>
              <span className="flex items-center gap-1.5 text-xs">
                <span className="w-2 h-2 rounded-full bg-[#22c55e]" />
                <span className="text-[#6b6b7b]">{formatNumber(totals.active_trucks)} Active</span>
              </span>
            </div>
            <div className="px-5 pb-5">
              <TruckMapPreview
                trucks={[]}
                clients={initialClients.map((client, index) => {
                  const [lat, lng] = getClientPosition(client.destination, index);
                  return { ...client, lat, lng };
                })}
                height={220}
                hideHeader
              />
            </div>
            <div className="px-5 pb-5 flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-1.5 text-xs text-[#6b6b7b]">
                <span className="w-2 h-2 rounded-full bg-[#7c3aed]" /> Optimized
              </div>
              <div className="flex items-center gap-1.5 text-xs text-[#6b6b7b]">
                <span className="w-2 h-2 rounded-full bg-[#f97316]" /> Standard
              </div>
              <Link href="/map" className="ml-auto text-xs text-[#7c3aed] font-medium hover:underline">
                View Full Map →
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-[#e8e5df]"
          >
            <h3 className="text-base font-semibold text-[#1a1a2e] mb-4">Transport today</h3>
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-xl bg-[#14b8a6]/10 flex items-center justify-center mb-3">
                <Boxes size={24} className="text-[#14b8a6]" />
              </div>
              <p className="text-2xl font-bold text-[#14b8a6]">{formatNumber(totals.tonnes)} t</p>
              <p className="text-sm text-[#6b6b7b] mb-4">gross weight over {formatNumber(totals.distance_km)} km</p>
              <div className="grid grid-cols-2 gap-3 w-full">
                <div className="rounded-xl bg-[#f8f7f3] p-3">
                  <p className="text-lg font-semibold text-[#1a1a2e]">{formatNumber(totals.positions_planned)}</p>
                  <p className="text-xs text-[#9e9aa4]">positions</p>
                </div>
                <div className="rounded-xl bg-[#f8f7f3] p-3">
                  <p className="text-lg font-semibold text-[#1a1a2e]">{formatNumber(totals.premium_trips)}</p>
                  <p className="text-xs text-[#9e9aa4]">premium (rented) trips</p>
                </div>
              </div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-[#e8e5df]"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-[#1a1a2e]">Planning Alerts</h3>
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
                        <p className="text-sm font-semibold text-[#1a1a2e]">{alert.title}</p>
                        <p className="text-xs text-[#6b6b7b] mt-0.5">{alert.description}</p>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
