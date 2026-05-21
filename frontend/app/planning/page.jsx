
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
                      className={`px-3 py-1 text-xs font-semibold rounded-full ${driverFilter === f.key ? 'bg-[#7c3aed] text-white' : 'text-[#6b6b7b] hover:bg-[#ecebee]'}`}
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
                  <div key={driver.id} className="flex items-center gap-4 rounded-3xl border border-[#eef0f2] bg-[#f8f7f3] p-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#ede9fe] text-sm font-semibold text-[#4c1d95]">{driver.avatar}</div>
                    <div className="min-w-0">
                      <p className="font-semibold text-[#1a1a2e] truncate">{driver.name}</p>
                      <p className="text-sm text-[#6b6b7b] truncate">{driver.vehicle}</p>
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
