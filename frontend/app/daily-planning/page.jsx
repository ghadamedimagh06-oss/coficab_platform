"use client";

import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { CalendarDays, Box, Truck, Clock3, ClipboardList } from 'lucide-react';
import { getDailyPlanningFromFile } from '../services/api';
import StatCard from '../../components/cards/StatCard';

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const WEEKDAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const REFRESH_INTERVAL = 30;

const STATUS_CONFIG = {
  completed:  { label: 'Completed',  cls: 'bg-emerald-50 text-emerald-700 border border-emerald-200' },
  in_transit: { label: 'In transit', cls: 'bg-blue-50   text-blue-700   border border-blue-200'   },
  pending:    { label: 'Pending',    cls: 'bg-amber-50  text-amber-700  border border-amber-200'  },
};

const PRIORITY_CONFIG = {
  urgent: { label: 'Urgent', cls: 'bg-rose-50   text-rose-700   border border-rose-200'   },
  high:   { label: 'High',   cls: 'bg-orange-50 text-orange-700 border border-orange-200' },
  normal: { label: 'Normal', cls: 'bg-[#f0ede8] text-muted'                          },
  low:    { label: 'Low',    cls: 'bg-slate-50  text-slate-500  border border-slate-200'  },
};

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function formatDate(date) {
  return date.toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });
}

function formatTime(date) {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export default function DailyPlanningPage() {
  const [allDeliveries, setAllDeliveries] = useState([]);
  const [selectedDay, setSelectedDay] = useState('');
  const [availableDays, setAvailableDays] = useState([]);
  const [dayCounts, setDayCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentTime, setCurrentTime] = useState('');
  const [currentDate, setCurrentDate] = useState('');
  const [todayName, setTodayName] = useState('');
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL);

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setCurrentTime(formatTime(now));
      setCurrentDate(formatDate(now));
      setTodayName(DAYS[now.getDay()]);
    };

    updateClock();
    const id = setInterval(updateClock, 1000);
    return () => clearInterval(id);
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDailyPlanningFromFile();
      const rows = Array.isArray(data) ? data : [];
      setAllDeliveries(rows);

      const counts = rows.reduce((acc, row) => {
        const day = row.delivery_day || 'Unknown';
        acc[day] = (acc[day] || 0) + 1;
        return acc;
      }, {});
      setDayCounts(counts);
      setAvailableDays(Object.keys(counts).sort((a, b) => {
        return WEEKDAY_ORDER.indexOf(a) - WEEKDAY_ORDER.indexOf(b);
      }));

      const defaultDay = counts[todayName] ? todayName : Object.keys(counts).sort((a, b) => {
        return WEEKDAY_ORDER.indexOf(a) - WEEKDAY_ORDER.indexOf(b);
      })[0] || todayName;
      setSelectedDay((current) => (current && counts[current] ? current : defaultDay));
    } catch {
      setError('Unable to load planning data from the application. Showing last known state.');
      setAllDeliveries([]);
      setDayCounts({});
      setSelectedDay(todayName);
    } finally {
      setLoading(false);
      setCountdown(REFRESH_INTERVAL);
    }
  }, [todayName]);

  // Initial load
  useEffect(() => { fetchData(); }, [fetchData]);

  // Auto-refresh countdown — reuses the live clock tick
  useEffect(() => {
    const id = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { fetchData(); return REFRESH_INTERVAL; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [fetchData]);

  const deliveries = useMemo(
    () => allDeliveries
      .filter((delivery) => delivery.delivery_day === selectedDay)
      .map((delivery) => ({
        ...delivery,
        comments:
          delivery.Comments ||
          delivery.comments ||
          delivery.note ||
          (delivery.special_instructions ? delivery.special_instructions : null) ||
          (delivery.status === 'pending' ? 'Waiting for dispatch' :
            delivery.status === 'in_transit' ? 'On the road' :
            delivery.status === 'completed' ? 'Delivered' :
            delivery.end_location ? `Destination: ${delivery.end_location}` : 'No comment'),
      })),

    [allDeliveries, selectedDay]
  );

  const stats = {
    total:      deliveries.length,
    completed:  deliveries.filter((d) => d.status === 'completed').length,
    in_transit: deliveries.filter((d) => d.status === 'in_transit').length,
    pending:    deliveries.filter((d) => d.status === 'pending').length,
  };

  return (
    <div className="p-8 min-h-screen bg-[#f5f5f7]">
      <motion.div variants={container} initial="hidden" animate="show" className="space-y-8">
        <motion.div variants={item} className="rounded-[2rem] border border-border bg-white p-8 shadow-sm">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-brand-600">Daily Planning</p>
              <h1 className="mt-3 text-4xl font-bold text-ink">Good morning, Ghada</h1>
              <p className="mt-2 text-sm leading-6 text-muted">Your delivery plan for the day, refreshed automatically from application data.</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <div suppressHydrationWarning={true} className="rounded-[1.75rem] border border-border bg-white px-6 py-5 text-center shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.32em] text-muted">Current time</p>
                <p className="mt-3 text-2xl font-semibold text-ink">{currentTime || 'Loading…'}</p>
              </div>
              <div suppressHydrationWarning={true} className="rounded-[1.75rem] border border-border bg-white px-6 py-5 text-center shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.32em] text-muted">Date</p>
                <p className="mt-3 text-lg font-semibold text-ink">{currentDate || 'Loading…'}</p>
              </div>
              <div className="rounded-[1.75rem] border border-border bg-white px-6 py-5 text-center shadow-sm">
                <p className="text-[11px] uppercase tracking-[0.32em] text-muted">Status</p>
                <p className={`mt-3 inline-flex rounded-full px-4 py-2 text-sm font-semibold ${loading ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'}`}>
                  {loading ? 'Refreshing…' : `Auto-refresh in ${countdown}s`}
                </p>
              </div>
            </div>
          </div>

          {error && (
            <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              {error}
            </div>
          )}
        </motion.div>

        <motion.div variants={container} className="grid gap-6 xl:grid-cols-[1.4fr_0.8fr]">
          <div className="space-y-6">
            <motion.div variants={item} className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-[1.75rem] bg-white p-6 border border-border shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
                <div className="flex items-center justify-between">
                  <div className="rounded-2xl bg-[#eef2ff] p-3 text-[#4338ca]">
                    <Box size={20} />
                  </div>
                </div>
                <p className="mt-5 text-sm uppercase tracking-[0.18em] text-muted">Deliveries</p>
                <p className="mt-2 text-3xl font-semibold text-ink">{stats.total}</p>
                <p className="mt-3 text-xs text-[#9e9aa4]">Selected day total</p>
              </div>
              <div className="rounded-[1.75rem] bg-white p-6 border border-border shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
                <div className="flex items-center justify-between">
                  <div className="rounded-2xl bg-[#ecfdf5] p-3 text-[#15803d]">
                    <Clock3 size={20} />
                  </div>
                </div>
                <p className="mt-5 text-sm uppercase tracking-[0.18em] text-muted">Pending</p>
                <p className="mt-2 text-3xl font-semibold text-ink">{stats.pending}</p>
                <p className="mt-3 text-xs text-[#9e9aa4]">Waiting to depart</p>
              </div>
              <div className="rounded-[1.75rem] bg-white p-6 border border-border shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
                <div className="flex items-center justify-between">
                  <div className="rounded-2xl bg-[#eff6ff] p-3 text-[#1d4ed8]">
                    <Truck size={20} />
                  </div>
                </div>
                <p className="mt-5 text-sm uppercase tracking-[0.18em] text-muted">In transit</p>
                <p className="mt-2 text-3xl font-semibold text-ink">{stats.in_transit}</p>
                <p className="mt-3 text-xs text-[#9e9aa4]">On the road now</p>
              </div>
              <div className="rounded-[1.75rem] bg-white p-6 border border-border shadow-sm transition hover:-translate-y-1 hover:shadow-lg">
                <div className="flex items-center justify-between">
                  <div className="rounded-2xl bg-[#fef3c7] p-3 text-[#b45309]">
                    <ClipboardList size={20} />
                  </div>
                </div>
                <p className="mt-5 text-sm uppercase tracking-[0.18em] text-muted">Completed</p>
                <p className="mt-2 text-3xl font-semibold text-ink">{stats.completed}</p>
                <p className="mt-3 text-xs text-[#9e9aa4]">Delivered successfully</p>
              </div>
            </motion.div>

            <motion.div variants={item} className="rounded-[2rem] border border-border bg-white shadow-sm overflow-hidden">
              <div className="flex flex-col gap-4 border-b border-border bg-canvas px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm uppercase tracking-[0.18em] text-muted">Daily planning — selected day</p>
                  <h2 className="text-2xl font-semibold text-ink">
                    {selectedDay || todayName} deliveries
                  </h2>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="rounded-full bg-[#eef2ff] px-3 py-2 text-sm font-semibold text-[#4338ca]">{deliveries.length} active deliveries</span>
                  <button
                    onClick={fetchData}
                    disabled={loading}
                    className="rounded-full border border-border bg-white px-5 py-2 text-sm font-semibold text-ink transition hover:bg-[#fafaff] disabled:opacity-50"
                  >
                    Refresh
                  </button>
                </div>
              </div>

              <div className="px-6 py-5">
                <div className="flex flex-wrap gap-3">
                  {availableDays.map((day) => (
                    <button
                      key={day}
                      type="button"
                      onClick={() => setSelectedDay(day)}
                      className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
                        selectedDay === day
                          ? 'bg-brand-600 text-white shadow-sm'
                          : 'bg-canvas text-ink border border-border hover:bg-white'
                      }`}
                    >
                      {day} ({dayCounts[day] || 0})
                    </button>
                  ))}
                </div>
              </div>

              {loading && (
                <div className="h-1 w-full bg-[#f0ede8]">
                  <div className="h-1 w-1/3 animate-pulse rounded-full bg-brand-600" />
                </div>
              )}

              {deliveries.length === 0 && !loading ? (
                <div className="py-16 text-center">
                  <p className="text-4xl">📭</p>
                  <p className="mt-4 text-lg font-medium text-ink">No deliveries scheduled for {selectedDay || todayName}</p>
                  <p className="mt-2 text-sm text-muted">Sync the planning file or refresh to update the latest schedule.</p>
                </div>
              ) : (
                <div className="overflow-x-auto rounded-[1.5rem] border border-border bg-white shadow-sm">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-border bg-canvas">
                        {['#', 'Client', 'Position', 'Comments', 'ETD', 'ETA', 'Dist (km)', 'Status', 'Priority'].map(
                          (col) => (
                            <th
                              key={col}
                              className="px-5 py-4 text-left text-[11px] font-semibold uppercase tracking-[0.18em] text-muted whitespace-nowrap"
                            >
                              {col}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border bg-white">
                      {deliveries.map((d, i) => {
                        const s = STATUS_CONFIG[d.status] ?? STATUS_CONFIG.pending;
                        const p = PRIORITY_CONFIG[d.priority] ?? PRIORITY_CONFIG.normal;
                        return (
                          <tr key={d.id ?? i} className="transition hover:bg-canvas">
                            <td className="px-5 py-4 text-muted">{d.row_number ?? i + 1}</td>
                            <td className="px-5 py-4 max-w-[220px]">
                              <span className="block truncate font-semibold text-ink" title={d.client || d.end_location}>
                                {d.client || d.end_location || '—'}
                              </span>
                            </td>
                            <td className="px-5 py-4 whitespace-nowrap text-right text-ink font-semibold">{d.quantity ?? '—'}</td>
                            <td className="px-5 py-4 max-w-[260px] overflow-hidden text-ink">
                              <span className="block truncate" title={d.comments || d.note || d.end_location || '—'}>
                                {d.comments || d.note || d.end_location || '—'}
                              </span>
                            </td>
                            <td className="px-5 py-4 whitespace-nowrap font-mono text-xs text-ink">{d.etd ?? '—'}</td>
                            <td className="px-5 py-4 whitespace-nowrap font-mono text-xs text-ink">{d.eta ?? '—'}</td>
                            <td className="px-5 py-4 whitespace-nowrap text-right text-ink">{d.distance_km != null ? d.distance_km.toFixed(1) : '—'}</td>
                            <td className="px-5 py-4 whitespace-nowrap">
                              <span className={`rounded-full px-3 py-1 text-xs font-medium ${s.cls}`}>{s.label}</span>
                            </td>
                            <td className="px-5 py-4 whitespace-nowrap">
                              <span className={`rounded-full px-3 py-1 text-xs font-medium ${p.cls}`}>{p.label}</span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {deliveries.length > 0 && !loading && (
                <div className="border-t border-border px-6 py-4 text-xs text-[#9e9eaa]">
                  {deliveries.length} deliveries shown · Data from <span className="font-medium text-muted">application database</span> with workbook fallback · auto-refreshes every {REFRESH_INTERVAL}s
                </div>
              )}
            </motion.div>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
