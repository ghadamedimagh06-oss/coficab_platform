"use client";

import { useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Truck,
  Route,
  AlertTriangle,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Download,
  Plus,
  MoreHorizontal,
  ChevronRight,
  Leaf,
  Bell,
  Clock,
} from 'lucide-react';
import {
  AreaChart,
  Area,
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
import {
  efficiencySegments,
  fleetData,
  timelineEvents,
  alerts,
  donutCenterText,
} from '../../data/dashboardData';
import { clients as initialClients, getClientPosition } from '../../data/coficabData';
import { useKpi } from '../../hooks/useKpi';
import { useWeeklyDeliveries } from '../../hooks/useWeeklyDeliveries';

const KPI_CARD_MAP = {
  'R4-06': { id: 'otif',  icon: 'truck',          iconBg: 'rgba(124,58,237,0.1)', iconColor: '#7c3aed' },
  'R4-02': { id: 'otd',   icon: 'route',           iconBg: 'rgba(59,130,246,0.1)', iconColor: '#3b82f6' },
  'R4-13': { id: 'fuel',  icon: 'alert-triangle',  iconBg: 'rgba(249,115,22,0.1)', iconColor: '#f97316' },
  'R4':    { id: 'load',  icon: 'bar-chart-3',     iconBg: 'rgba(20,184,166,0.1)', iconColor: '#14b8a6' },
};

function toCardShape(kpi) {
  const meta = KPI_CARD_MAP[kpi.code] ?? { id: kpi.code, icon: 'bar-chart-3', iconBg: 'rgba(124,58,237,0.1)', iconColor: '#7c3aed' };
  const val = kpi.value !== null && kpi.value !== undefined
    ? (kpi.unit === '%' ? `${kpi.value.toFixed(1)}%`
      : kpi.unit === '€/T' ? `${kpi.value.toFixed(1)} €/T`
      : kpi.unit === 'EUR' ? `${kpi.value.toFixed(0)} €`
      : `${kpi.value}`)
    : '—';
  return {
    id: meta.id,
    label: kpi.label,
    value: val,
    icon: meta.icon,
    iconBg: meta.iconBg,
    iconColor: meta.iconColor,
    trend: kpi.trend ?? 0,
    trendLabel: 'vs last month',
    sparklineData: [],
  };
}

function toWeeklyShape(row) {
  return { day: row.week, delivered: row.delivered, planned: row.total };
}

const TruckMapPreview = dynamic(() => import('../../components/map/TruckMap'), { ssr: false });

const iconMap = {
  truck: Truck,
  route: Route,
  'alert-triangle': AlertTriangle,
  'bar-chart-3': BarChart3,
};

const alertIconMap = {
  'alert-triangle': AlertTriangle,
  clock: Clock,
  info: Bell,
};

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-3 border border-[#e8e5df] text-sm">
        <p className="font-semibold text-[#1a1a2e] mb-1">{label}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-2 text-xs">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-[#6b6b7b]">{entry.name}:</span>
            <span className="font-semibold text-[#1a1a2e]">{entry.value}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

export default function DashboardPage() {
  const [period, setPeriod] = useState('Week');
  const { kpis, isLoading: kpiLoading } = useKpi();
  const { weeks } = useWeeklyDeliveries(7);

  // KPI stat cards — show only the 4 that have a card mapping
  const kpiData = kpis
    .filter((k) => k.code in KPI_CARD_MAP)
    .map(toCardShape);
  // Fall back to loading placeholders while fetching
  const displayKpis = kpiData.length > 0 ? kpiData : [
    { id: 'otif', label: 'OTIF', value: '—', icon: 'truck', iconBg: 'rgba(124,58,237,0.1)', iconColor: '#7c3aed', trend: 0, trendLabel: '…', sparklineData: [] },
    { id: 'otd',  label: 'OTD',  value: '—', icon: 'route', iconBg: 'rgba(59,130,246,0.1)', iconColor: '#3b82f6', trend: 0, trendLabel: '…', sparklineData: [] },
    { id: 'fuel', label: 'Fuel Efficiency', value: '—', icon: 'alert-triangle', iconBg: 'rgba(249,115,22,0.1)', iconColor: '#f97316', trend: 0, trendLabel: '…', sparklineData: [] },
    { id: 'load', label: 'Load Efficiency', value: '—', icon: 'bar-chart-3', iconBg: 'rgba(20,184,166,0.1)', iconColor: '#14b8a6', trend: 0, trendLabel: '…', sparklineData: [] },
  ];

  // Weekly chart — fall back to empty mock shape while loading
  const weeklyData = weeks.length > 0
    ? weeks.map(toWeeklyShape)
    : [
        { day: 'Mon', delivered: 0, planned: 0 },
        { day: 'Tue', delivered: 0, planned: 0 },
        { day: 'Wed', delivered: 0, planned: 0 },
        { day: 'Thu', delivered: 0, planned: 0 },
        { day: 'Fri', delivered: 0, planned: 0 },
        { day: 'Sat', delivered: 0, planned: 0 },
        { day: 'Sun', delivered: 0, planned: 0 },
      ];

  return (
    <div className="p-8 min-h-screen bg-[#f8f7f3]">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between mb-8"
      >
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Operations dashboard</p>
          <h1 className="mt-3 text-4xl font-bold text-[#1a1a2e]">Good morning, Ghada</h1>
          <p className="mt-2 text-sm text-[#6b6b7b]">Wednesday, May 20, 2026 · Overview of fleet, routes and delivery performance.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          {['Week', 'Month', 'Year'].map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setPeriod(option)}
              className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
                period === option
                  ? 'bg-[#7c3aed] text-white shadow-sm'
                  : 'bg-white text-[#6b6b7b] border border-[#e8e5df] hover:bg-[#f5f3ff]'
              }`}
            >
              {option}
            </button>
          ))}
          <button className="inline-flex items-center gap-2 rounded-2xl border border-[#e8e5df] bg-white px-4 py-2 text-sm font-semibold text-[#1a1a2e] hover:bg-[#faf8f5] transition">
            <Download size={16} />
            Export
          </button>
          <button className="inline-flex items-center gap-2 rounded-2xl bg-[#7c3aed] px-5 py-2 text-sm font-semibold text-white hover:bg-[#6d28d9] transition shadow-sm">
            <Plus size={16} />
            New Route
          </button>
        </div>
      </motion.div>

      <motion.div variants={container} initial="hidden" animate="show" className="grid gap-6 xl:grid-cols-4 mb-8">
        {displayKpis.map((kpi) => {
          const Icon = iconMap[kpi.icon] || BarChart3;
          const isPositive = kpi.trend >= 0;
          return (
            <motion.div
              key={kpi.id}
              variants={item}
              whileHover={{ y: -3, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
              className="bg-white rounded-2xl p-6 border border-[#e8e5df] cursor-pointer transition-shadow"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: kpi.iconBg }}>
                  <Icon size={20} color={kpi.iconColor} />
                </div>
                <button className="text-[#9e9ea4] hover:text-[#6b6b7b]"><MoreHorizontal size={18} /></button>
              </div>
              <p className="text-sm text-[#6b6b7b] mb-1">{kpi.label}</p>
              <p className="text-4xl font-bold text-[#1a1a2e] mb-3">{kpi.value}</p>
              <div className="h-10 mb-3">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={kpi.sparklineData.map((value, index) => ({ value, index }))}>
                    <defs>
                      <linearGradient id={`grad-${kpi.id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={kpi.iconColor} stopOpacity={0.2} />
                        <stop offset="100%" stopColor={kpi.iconColor} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="value" stroke={kpi.iconColor} strokeWidth={2} fill={`url(#grad-${kpi.id})`} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="flex items-center gap-1.5">
                {isPositive ? (
                  <TrendingUp size={14} className="text-[#22c55e]" />
                ) : (
                  <TrendingDown size={14} className="text-[#ef4444]" />
                )}
                <span className="text-sm font-medium text-[#22c55e]">{isPositive ? '+' : ''}{kpi.trend}%</span>
                <span className="text-xs text-[#9e9aa4]">{kpi.trendLabel}</span>
              </div>
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
                <p className="text-sm text-[#6b6b7b]">Deliveries vs. Planned</p>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={weeklyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0ede8" vertical={false} />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#9e9ea4', fontSize: 12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9e9ea4', fontSize: 12 }} domain={[0, 200]} />
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
                <span className="text-sm text-[#6b6b7b]">Planned</span>
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
              <button className="text-sm font-semibold text-[#7c3aed] hover:text-[#5b21b6]">View reports</button>
            </div>
            <div className="space-y-4">
              {fleetData.map((vehicle) => {
                const fillColor = vehicle.utilization >= 90 ? '#22c55e' : vehicle.utilization >= 80 ? '#f59e0b' : '#ef4444';
                return (
                  <div key={vehicle.name} className="space-y-2">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="font-semibold text-[#1a1a2e]">{vehicle.name}</p>
                        <p className="text-sm text-[#6b6b7b] mt-1">{vehicle.type}</p>
                      </div>
                      <p className="text-sm font-semibold" style={{ color: fillColor }}>{vehicle.utilization}%</p>
                    </div>
                    <div className="h-2 rounded-full bg-[#f0ede8] overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${vehicle.utilization}%`, backgroundColor: fillColor }} />
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
              <button className="text-sm text-[#7c3aed] font-medium hover:underline">
                View All <ChevronRight size={14} className="inline" />
              </button>
            </div>
            <div className="space-y-4">
              {timelineEvents.map((event, index) => (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 + 0.3 }}
                  className="flex gap-4 relative"
                >
                  {index < timelineEvents.length - 1 && (
                    <div className="absolute left-[7px] top-6 w-0.5 h-full bg-[#e8e5df]" />
                  )}
                  <div className="flex flex-col items-center">
                    <div
                      className="w-4 h-4 rounded-full border-2 flex-shrink-0 mt-1"
                      style={{
                        backgroundColor:
                          event.status === 'completed'
                            ? '#22c55e'
                            : event.status === 'in-transit'
                            ? '#3b82f6'
                            : event.status === 'delayed'
                            ? '#ef4444'
                            : '#7c3aed',
                        borderColor:
                          event.status === 'completed'
                            ? '#dcfce7'
                            : event.status === 'in-transit'
                            ? '#dbeafe'
                            : event.status === 'delayed'
                            ? '#fee2e2'
                            : '#f5f3ff',
                      }}
                    />
                  </div>
                  <div className="flex-1 pb-5">
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="text-sm font-semibold text-[#1a1a2e]">{event.route}</span>
                        <p className="text-sm text-[#6b6b7b] mt-0.5">{event.description}</p>
                        <p className="text-xs text-[#9e9aa4] mt-1">{event.time}</p>
                      </div>
                      <StatusBadge status={event.status === 'in-transit' ? 'in_transit' : event.status === 'completed' ? 'completed' : 'pending'} size="sm" />
                    </div>
                  </div>
                </motion.div>
              ))}
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
              <button className="text-[#9e9aa4] hover:text-[#6b6b7b]">
                <Download size={16} />
              </button>
            </div>
            <div className="flex flex-col items-center">
              <div className="relative w-48 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={efficiencySegments}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                      startAngle={90}
                      endAngle={-270}
                    >
                      {efficiencySegments.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-3xl font-bold text-[#1a1a2e]">{donutCenterText.value}</span>
                  <span className="text-xs text-[#9e9aa4]">{donutCenterText.label}</span>
                </div>
              </div>
              <div className="flex items-center gap-4 mt-4 flex-wrap justify-center">
                {efficiencySegments.map((seg) => (
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
                <span className="text-[#6b6b7b]">12 Active</span>
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
              <div className="flex items-center gap-1.5 text-xs text-[#6b6b7b]">
                <span className="w-2 h-2 rounded-full bg-[#ef4444]" /> Delayed
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
            <h3 className="text-base font-semibold text-[#1a1a2e] mb-4">CO₂ Reduction</h3>
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-xl bg-[#14b8a6]/10 flex items-center justify-center mb-3">
                <Leaf size={24} className="text-[#14b8a6]" />
              </div>
              <p className="text-2xl font-bold text-[#14b8a6]">2.4 tonnes</p>
              <p className="text-sm text-[#6b6b7b] mb-4">saved this month</p>
              <div className="w-full h-2 bg-[#f0ede8] rounded-full overflow-hidden mb-2">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: '78%' }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                  className="h-full bg-[#14b8a6] rounded-full"
                />
              </div>
              <p className="text-xs text-[#9e9aa4] mb-4">78% of monthly target</p>
              <p className="text-sm text-[#6b6b7b] italic">
                Equivalent to planting <span className="font-semibold text-[#14b8a6]">120 trees</span>
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.15 }}
            className="bg-white rounded-2xl p-6 border border-[#e8e5df]"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-[#1a1a2e]">Real-time Alerts</h3>
              <span className="text-xs font-semibold bg-[#f97316] text-white rounded-md px-2 py-0.5">3</span>
            </div>
            <div className="space-y-3">
              {alerts.map((alert) => {
                const AlertIcon = alertIconMap[alert.icon] || Bell;
                return (
                  <motion.div
                    key={alert.id}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="p-3 rounded-xl border-l-[3px]"
                    style={{
                      backgroundColor: alert.bgColor,
                      borderLeftColor: alert.borderColor,
                    }}
                  >
                    <div className="flex items-start gap-3">
                      <AlertIcon size={18} style={{ color: alert.borderColor }} className="flex-shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-[#1a1a2e]">{alert.title}</p>
                        <p className="text-xs text-[#6b6b7b] mt-0.5">{alert.description}</p>
                        <p className="text-xs text-[#9e9aa4] mt-1">{alert.time}</p>
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
