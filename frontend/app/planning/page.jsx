
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
  const [driverFilter, setDriverFilter] = useState('all');
  const filteredDrivers = useMemo(() => drivers.filter((d) => (driverFilter === 'all' ? true : d.status === driverFilter)), [driverFilter]);

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
    <div className="min-h-screen p-8 bg-canvas">
      <div className="mb-8 flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-brand-600">Planning command center</p>
          <h1 className="mt-3 text-4xl font-bold text-ink">Route planning hub</h1>
          <p className="mt-2 text-sm text-muted">Monitor daily schedules, manage groupage opportunities, and keep routes on time.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button className="inline-flex items-center gap-2 rounded-2xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition">
            <Plus size={16} />
            Add route
          </button>
          <button className="inline-flex items-center gap-2 rounded-2xl border border-border bg-white px-4 py-2 text-sm font-semibold text-ink hover:bg-canvas transition">
            <CalendarDays size={16} />
            Weekly view
          </button>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.45fr_0.95fr]">
        <section className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="rounded-[2rem] border border-border bg-white p-5 shadow-sm">
              <p className="text-sm text-muted">Total routes</p>
              <p className="mt-3 text-3xl font-semibold text-ink">{routeSummary.routes}</p>
            </div>
            <div className="rounded-[2rem] border border-border bg-white p-5 shadow-sm">
              <p className="text-sm text-muted">In progress</p>
              <p className="mt-3 text-3xl font-semibold text-ink">{routeSummary.active}</p>
            </div>
            <div className="rounded-[2rem] border border-border bg-white p-5 shadow-sm">
              <p className="text-sm text-muted">Delayed</p>
              <p className="mt-3 text-3xl font-semibold text-ink">{routeSummary.delayed}</p>
            </div>
            <div className="rounded-[2rem] border border-border bg-white p-5 shadow-sm">
              <p className="text-sm text-muted">Stops today</p>
              <p className="mt-3 text-3xl font-semibold text-ink">{routeSummary.stops}</p>
            </div>
          </div>

          <div className="rounded-[2rem] border border-border bg-white p-6 shadow-sm">
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-muted">Day selector</p>
                <h2 className="text-2xl font-semibold text-ink">Weekly route snapshot</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {weekDays.map((day) => (
                  <button
                    key={day.dayName}
                    onClick={() => setActiveDay(day.dayName)}
                    className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${activeDay === day.dayName ? 'bg-brand-600 text-white' : 'bg-[#f4f3f1] text-muted hover:bg-[#e7e5dd]'}`}
                  >
                    {day.dayName}
                  </button>
                ))}
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {weekDays.map((day) => (
                <div key={day.dayName} className={`rounded-3xl p-4 ${activeDay === day.dayName ? 'bg-brand-600/10 border border-brand-600' : 'bg-canvas'}`}>
                  <p className="text-sm font-semibold text-ink">{day.dayName}</p>
                  <p className="mt-1 text-4xl font-bold text-ink">{day.routeCount}</p>
                  <p className="mt-2 text-sm text-muted">Routes scheduled</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-border bg-white p-6 shadow-sm">
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-muted">Route list</p>
                <h2 className="text-2xl font-semibold text-ink">Active deliveries</h2>
              </div>
              <div className="inline-flex items-center gap-2 rounded-2xl bg-[#f4f3f1] px-4 py-2 text-sm font-semibold text-muted">
                <Truck size={16} /> Today
              </div>
            </div>
            <div className="divide-y divide-[#eef0f2]">
              {routeBlocks.map((route) => (
                <div key={route.id} className="grid gap-3 py-5 sm:grid-cols-[1.2fr_0.9fr_0.7fr_0.6fr] items-center">
                  <div>
                    <p className="font-semibold text-ink">{route.routeId}</p>
                    <p className="text-sm text-muted mt-1">{route.name}</p>
                  </div>
                  <div>
                    <p className="font-semibold text-ink">{route.startTime} - {route.endTime}</p>
                    <p className="text-sm text-muted mt-1">{route.stops} stops · {route.capacity}% capacity</p>
                  </div>
                  <div>
                    <p className="font-semibold text-ink">{route.groupage} groupage</p>
                    <p className="text-sm text-muted mt-1">{route.driverId}</p>
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
          <div className="rounded-[2rem] border border-border bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-muted">Driver capacity</p>
                <h2 className="text-2xl font-semibold text-ink">Assigned drivers</h2>
              </div>
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-2 rounded-full bg-[#eff6ff] px-3 py-1 text-sm font-semibold text-[#3b82f6]">
                  <Users size={14} /> {filteredDrivers.length}
                </span>
                <div className="inline-flex items-center gap-2 rounded-2xl bg-[#f4f3f1] p-1">
                  {[
                    { key: 'all', label: 'Tous' },
                    { key: 'available', label: 'Disponible' },
                    { key: 'pause', label: 'Pause' },
                    { key: 'on-route', label: 'Sur route' },
                  ].map((f) => (
                    <button
                      key={f.key}
                      onClick={() => setDriverFilter(f.key)}
                      className={`px-3 py-1 text-xs font-semibold rounded-full ${driverFilter === f.key ? 'bg-brand-600 text-white' : 'text-muted hover:bg-[#ecebee]'}`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="space-y-4">
              {drivers
                .filter((d) => (driverFilter === 'all' ? true : d.status === driverFilter))
                .map((driver) => (
                  <div key={driver.id} className="flex items-center gap-4 rounded-3xl border border-[#eef0f2] bg-canvas p-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-100 text-sm font-semibold text-brand-900">{driver.avatar}</div>
                    <div className="min-w-0">
                      <p className="font-semibold text-ink truncate">{driver.name}</p>
                      <p className="text-sm text-muted truncate">{driver.vehicle}</p>
                      <div className="mt-2">
                        <span className={`inline-flex items-center gap-2 rounded-full px-2 py-0.5 text-xs font-semibold ${driver.status === 'on-route' ? 'bg-[#eff6ff] text-[#3b82f6]' : driver.status === 'available' ? 'bg-[#ecfdf5] text-[#16a34a]' : 'bg-[#fff7ed] text-[#f97316]'}`}>
                          <span className={`inline-block h-2 w-2 rounded-full ${driver.status === 'on-route' ? 'bg-[#3b82f6]' : driver.status === 'available' ? 'bg-[#16a34a]' : 'bg-[#f97316]'}`} />
                          {driver.status === 'on-route' ? 'Sur route' : driver.status === 'available' ? 'Disponible' : 'Pause'}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-border bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-muted">Priority recommendations</p>
                <h2 className="text-2xl font-semibold text-ink">Optimization suggestions</h2>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full bg-[#ecfdf5] px-3 py-1 text-sm font-semibold text-[#16a34a]">
                <Sparkles size={14} /> Smart
              </span>
            </div>
            <div className="space-y-4">
              {suggestions.map((suggestion) => (
                <div key={suggestion.id} className="rounded-3xl border border-[#eef0f2] bg-canvas p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-ink">{suggestion.title}</p>
                      <p className="text-sm text-muted mt-1">{suggestion.description}</p>
                    </div>
                    <AlertTriangle size={18} className="text-[#f97316]" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-border bg-white p-6 shadow-sm">
            <div className="mb-5 flex items-center justify-between gap-4">
              <div>
                <p className="text-sm text-muted">Groupage insights</p>
                <h2 className="text-2xl font-semibold text-ink">Shared loads</h2>
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
                      <p className="font-semibold text-ink">{group.name}</p>
                      <p className="text-sm text-muted mt-1">{group.clientCount} clients · {group.routeId}</p>
                    </div>
                    <ArrowRight size={18} className="text-brand-600" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>

      <div className="mt-6 rounded-[2rem] border border-border bg-white p-6 shadow-sm">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm text-muted">Communication feed</p>
            <h2 className="text-2xl font-semibold text-ink">Planning activity</h2>
          </div>
          <button className="inline-flex items-center gap-2 rounded-2xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition">
            <ShieldCheck size={16} /> Confirm audit
          </button>
        </div>
        <ChatPanel
          messages={chatMessages}
          title="Planning Copilot"
          context={{
            page: 'planning',
            activeDay,
            routeSummary,
            routes: routeBlocks,
            drivers: filteredDrivers,
            groupages,
          }}
        />
      </div>
    </div>
  );
}
