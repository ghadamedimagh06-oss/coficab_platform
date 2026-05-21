from pathlib import Path

base = Path(__file__).resolve().parent.parent

dashboard_content = """
"use client";

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Download,
  Plus,
  MoreHorizontal,
  ChevronRight,
  Leaf,
  Truck,
  Route,
  AlertTriangle,
  BarChart3,
  TrendingUp,
  TrendingDown,
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
  kpiData,
  weeklyData,
  efficiencySegments,
  fleetData,
  timelineEvents,
  alerts,
  donutCenterText,
} from '../../data/dashboardData';

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

function CustomTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white rounded-2xl border border-[#e8e5df] p-3 shadow-sm text-sm">
        <p className="font-semibold text-[#1a1a2e] mb-2">{label}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-2 text-xs text-[#6b6b7b]">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span>{entry.name}</span>
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

  return (
    <div className="min-h-screen p-8 bg-[#f8f7f3]">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-8 flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Operations dashboard</p>
          <h1 className="mt-3 text-4xl font-bold text-[#1a1a2e]">Good morning, John</h1>
          <p className="mt-2 text-sm text-[#6b6b7b]">Monday, December 24, 2024 · Overview of fleet, routes and delivery performance.</p>
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

      <motion.div initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.08 } } }} className="grid gap-6 xl:grid-cols-4 mb-8">
        {kpiData.map((kpi) => {
          const Icon = iconMap[kpi.icon] || BarChart3;
          const isPositive = kpi.trend >= 0;
          return (
            <motion.div key={kpi.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} whileHover={{ y: -3 }} className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between mb-5">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl" style={{ backgroundColor: kpi.iconBg }}>
                  <Icon size={20} color={kpi.iconColor} />
                </span>
                <button className="text-[#9e9ea4] hover:text-[#6b6b7b]"><MoreHorizontal size={18} /></button>
              </div>
              <p className="text-sm text-[#6b6b7b] mb-2">{kpi.label}</p>
              <p className="text-3xl font-semibold text-[#1a1a2e] mb-3">{kpi.value}</p>
              <div className="h-16">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={kpi.sparklineData.map((value, index) => ({ value, index }))}>
                    <defs>
                      <linearGradient id={`gradient-${kpi.id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={kpi.iconColor} stopOpacity={0.28} />
                        <stop offset="95%" stopColor={kpi.iconColor} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="value" stroke={kpi.iconColor} fill={`url(#gradient-${kpi.id})`} strokeWidth={2.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 flex items-center gap-2 text-sm">
                {isPositive ? <TrendingUp size={16} className="text-[#16a34a]" /> : <TrendingDown size={16} className="text-[#dc2626]" />}
                <span className={`font-semibold ${isPositive ? 'text-[#16a34a]' : 'text-[#dc2626]'}`}>{isPositive ? '+' : ''}{kpi.trend}%</span>
                <span className="text-[#6b6b7b]">{kpi.trendLabel}</span>
              </div>
            </motion.div>
          );
        })}
      </motion.div>

      <div className="grid gap-6 xl:grid-cols-[1.8fr_1fr]">
        <div className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-[#6b6b7b]">Operational snapshot</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Delivery performance</h2>
              </div>
              <span className="rounded-full bg-[#f0ede8] px-3 py-2 text-sm text-[#6b6b7b]">Real-time</span>
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={weeklyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e7e5dd" vertical={false} />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: '#9e9ea4', fontSize: 12 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9e9ea4', fontSize: 12 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="delivered" name="Delivered" barSize={24} radius={[8, 8, 0, 0]} fill="#7c3aed" />
                  <Line type="monotone" dataKey="planned" stroke="#f97316" strokeWidth={3} dot={{ r: 4, fill: '#f97316', strokeWidth: 0 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-5 flex flex-wrap gap-4 text-sm text-[#6b6b7b]">
              <span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#7c3aed]" />Delivered</span>
              <span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#f97316]" />Planned</span>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
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
                      <div className="h-full rounded-full" style={{ width: f"{vehicle.utilization}%", backgroundColor: fillColor }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        </div>

        <aside className="space-y-6">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4 mb-5">
              <div>
                <p className="text-sm text-[#6b6b7b]">Efficiency score</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">{donutCenterText.value}</h2>
              </div>
              <div className="w-20 h-20">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={efficiencySegments} innerRadius={38} outerRadius={48} dataKey="value" startAngle={90} endAngle={-270}>
                      {efficiencySegments.map((entry, index) => (
                        <Cell key={index} fill={entry.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="flex flex-col gap-3">
              {efficiencySegments.map((segment) => (
                <div key={segment.name} className="flex items-center gap-3">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: segment.color }} />
                  <p className="text-sm text-[#1a1a2e] font-semibold">{segment.name}</p>
                  <span className="ml-auto text-sm text-[#6b6b7b]">{segment.value}%</span>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <p className="text-sm text-[#6b6b7b]">Route status</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Live alerts</h2>
              </div>
              <span className="text-sm font-semibold text-[#7c3aed]">{alerts.length} open</span>
            </div>
            <div className="space-y-4">
              {alerts.map((alert) => {
                const Icon = alertIconMap[alert.icon] || Bell;
                return (
                  <div key={alert.id} className="rounded-3xl border border-[#e8e5df] bg-[#fff7ed] p-4">
                    <div className="flex items-start gap-3">
                      <span className="mt-1 text-[#ef4444]"><Icon size={18} /></span>
                      <div>
                        <p className="font-semibold text-[#1a1a2e]">{alert.title}</p>
                        <p className="text-sm text-[#6b6b7b] mt-1">{alert.description}</p>
                        <p className="text-xs text-[#9e9ea4] mt-2">{alert.time}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-[#6b6b7b]">Audit readiness</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Compliance active</h2>
              </div>
              <StatusBadge status="completed" size="sm" />
            </div>
            <p className="text-sm text-[#6b6b7b]">All planning decisions are logged in the platform with a full change trail.</p>
          </motion.div>
        </aside>
      </div>
    </div>
  );
}
"""

planning_content = """
"use client";

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  CalendarDays,
  Layers,
  ArrowRight,
  AlertTriangle,
  Truck,
  Users,
  Sparkles,
  Plus,
  ShieldCheck,
} from 'lucide-react';
import StatusBadge from '../../components/shared/StatusBadge';
import ChatPanel from '../../components/chat/ChatPanel';
import {
  drivers,
  routeBlocks,
  weekDays,
  suggestions,
  groupages,
} from '../../data/planningData';

export default function PlanningPage() {
  const [activeDay, setActiveDay] = useState('Mon');
  const [chatMessages, setChatMessages] = useState([
    'Planning board ready. Review route assignments and groupage alerts.',
  ]);

  const routeSummary = useMemo(
    () => ({
      routes: routeBlocks.length,
      active: routeBlocks.filter((route) => route.status === 'in-progress').length,
      delayed: routeBlocks.filter((route) => route.status === 'delayed').length,
      stops: routeBlocks.reduce((sum, route) => sum + route.stops, 0),
    }),
    []
  );

  return (
    <div className="min-h-screen p-8 bg-[#f8f7f3]">
      <div className="mb-8 flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Planning command center</p>
          <h1 className="mt-3 text-4xl font-bold text-[#1a1a2e]">Route planning hub</h1>
          <p className="mt-2 text-sm text-[#6b6b7b]">Monitor daily schedules, manage groupage opportunities, and keep routes on time.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button className="inline-flex items-center gap-2 rounded-2xl bg-[#7c3aed] px-4 py-2 text-sm font-semibold text-white hover:bg-[#6d28d9] transition">
            <Plus size={16} />
            Add route
          </button>
          <button className="inline-flex items-center gap-2 rounded-2xl border border-[#e8e5df] bg-white px-4 py-2 text-sm font-semibold text-[#1a1a2e] hover:bg-[#faf8f5] transition">
            <CalendarDays size={16} />
            Weekly view
          </button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
        <section className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <p className="text-sm text-[#6b6b7b]">Total routes</p>
              <p className="mt-3 text-3xl font-semibold text-[#1a1a2e]">{routeSummary.routes}</p>
            </div>
            <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <p className="text-sm text-[#6b6b7b]">In progress</p>
              <p className="mt-3 text-3xl font-semibold text-[#1a1a2e]">{routeSummary.active}</p>
            </div>
            <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <p className="text-sm text-[#6b6b7b]">Delayed</p>
              <p className="mt-3 text-3xl font-semibold text-[#1a1a2e]">{routeSummary.delayed}</p>
            </div>
            <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <p className="text-sm text-[#6b6b7b]">Stops today</p>
              <p className="mt-3 text-3xl font-semibold text-[#1a1a2e]">{routeSummary.stops}</p>
            </div>
          </div>

          <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-[#6b6b7b]">Day selector</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Weekly route snapshot</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {weekDays.map((day) => (
                  <button
                    key={day.dayName}
                    onClick={() => setActiveDay(day.dayName)}
                    className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${activeDay === day.dayName ? 'bg-[#7c3aed] text-white' : 'bg-[#f4f3f1] text-[#6b6b7b] hover:bg-[#e7e5dd]'}`}
                  >
                    {day.dayName}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {weekDays.map((day) => (
                <div key={day.dayName} className={`rounded-3xl p-4 ${activeDay === day.dayName ? 'bg-[#7c3aed]/10 border border-[#7c3aed]' : 'bg-[#f8f7f3]'}`}>
                  <p className="text-sm font-semibold text-[#1a1a2e]">{day.dayName}</p>
                  <p className="mt-1 text-4xl font-bold text-[#1a1a2e]">{day.routeCount}</p>
                  <p className="mt-2 text-sm text-[#6b6b7b]">Routes scheduled</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-[#6b6b7b]">Route list</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Active deliveries</h2>
              </div>
              <div className="inline-flex items-center gap-2 rounded-2xl bg-[#f4f3f1] px-4 py-2 text-sm font-semibold text-[#6b6b7b]">
                <Truck size={16} /> Today
              </div>
            </div>
            <div className="divide-y divide-[#eef0f2]">
              {routeBlocks.map((route) => (
                <div key={route.id} className="grid gap-3 py-5 sm:grid-cols-[1.2fr_0.9fr_0.7fr_0.6fr] items-center">
                  <div>
                    <p className="font-semibold text-[#1a1a2e]">{route.routeId}</p>
                    <p className="text-sm text-[#6b6b7b] mt-1">{route.name}</p>
                  </div>
                  <div>
                    <p className="font-semibold text-[#1a1a2e]">{route.startTime} - {route.endTime}</p>
                    <p className="text-sm text-[#6b6b7b] mt-1">{route.stops} stops · {route.capacity}% capacity</p>
                  </div>
                  <div>
                    <p className="font-semibold text-[#1a1a2e]">{route.groupage} groupage</p>
                    <p className="text-sm text-[#6b6b7b] mt-1">{route.driverId}</p>
                  </div>
                  <div className="flex items-center justify-end gap-2">
                    <StatusBadge status={route.status} size="sm" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <aside className="space-y-6">
          <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-[#6b6b7b]">Driver capacity</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Assigned drivers</h2>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full bg-[#eff6ff] px-3 py-1 text-sm font-semibold text-[#3b82f6]">
                <Users size={14} /> {drivers.length}
              </span>
            </div>
            <div className="space-y-4">
              {drivers.slice(0, 5).map((driver) => (
                <div key={driver.id} className="flex items-center gap-4 rounded-3xl border border-[#eef0f2] bg-[#f8f7f3] p-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#ede9fe] text-sm font-semibold text-[#4c1d95]">{driver.avatar}</div>
                  <div className="min-w-0">
                    <p className="font-semibold text-[#1a1a2e] truncate">{driver.name}</p>
                    <p className="text-sm text-[#6b6b7b] truncate">{driver.vehicle}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-[#6b6b7b]">Priority recommendations</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Optimization suggestions</h2>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full bg-[#ecfdf5] px-3 py-1 text-sm font-semibold text-[#16a34a]">
                <Sparkles size={14} /> Smart
              </span>
            </div>
            <div className="space-y-4">
              {suggestions.map((suggestion) => (
                <div key={suggestion.id} className="rounded-3xl border border-[#eef0f2] bg-[#f8f7f3] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-[#1a1a2e]">{suggestion.title}</p>
                      <p className="text-sm text-[#6b6b7b] mt-1">{suggestion.description}</p>
                    </div>
                    <AlertTriangle size={18} className="text-[#f97316]" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-[#6b6b7b]">Groupage insights</p>
                <h2 className="text-2xl font-semibold text-[#1a1a2e]">Shared loads</h2>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full bg-[#f8fafc] px-3 py-1 text-sm font-semibold text-[#0f766e]">
                <Layers size={14} /> {groupages.length}
              </span>
            </div>
            <div className="space-y-4">
              {groupages.map((group) => (
                <div key={group.id} className="rounded-3xl border border-[#eef0f2] bg-[#fcf6ff] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-[#1a1a2e]">{group.name}</p>
                      <p className="text-sm text-[#6b6b7b] mt-1">{group.clientCount} clients · {group.routeId}</p>
                    </div>
                    <ArrowRight size={18} className="text-[#7c3aed]" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>

      <div className="mt-6 rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm text-[#6b6b7b]">Communication feed</p>
            <h2 className="text-2xl font-semibold text-[#1a1a2e]">Planning activity</h2>
          </div>
          <button className="inline-flex items-center gap-2 rounded-2xl bg-[#7c3aed] px-4 py-2 text-sm font-semibold text-white hover:bg-[#6d28d9] transition">
            <ShieldCheck size={16} /> Confirm audit
          </button>
        </div>
        <ChatPanel messages={chatMessages} />
      </div>
    </div>
  );
}
"""

(Path(base) / 'app' / 'dashboard' / 'page.jsx').write_text(dashboard_content, encoding='utf-8')
(Path(base) / 'app' / 'planning' / 'page.jsx').write_text(planning_content, encoding='utf-8')
