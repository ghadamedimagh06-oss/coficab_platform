"use client";

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, Truck, Clock, MapPin, AlertCircle, TrendingDown, CheckCircle } from 'lucide-react';
import { trucks, getClientPosition } from '../../data/coficabData';
import { getDailyPlanningFromFile, generatePlanning } from '../services/api';

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

function formatTime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`;
}

export default function GeneratedPlanningPage() {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expandedRoute, setExpandedRoute] = useState(0);
  const [selectedDay, setSelectedDay] = useState('');

  // Données simulées (fallback)
  const mockPlan = {
    status: 'success',
    algorithm: 'VRPTW Complete (K-Means + FFD + NN + Time Windows)',
    routes: [
      {
        truck_id: 'Camion001',
        stops: [
          { client_id: 1, client_name: 'Alami Pharma', arrival_time: 495, departure_time: 510, status: 'OK' },
          { client_id: 2, client_name: 'Maghreb Textiles', arrival_time: 540, departure_time: 555, status: 'OK' },
          { client_id: 3, client_name: 'Atlas Electronics', arrival_time: 570, departure_time: 585, status: 'OK' },
        ],
        start_time: 480,
        end_time: 610,
        total_distance: 35.5,
        total_cost: 67.75,
      },
      {
        truck_id: 'Camion002',
        stops: [
          { client_id: 4, client_name: 'Royal Ceramics', arrival_time: 490, departure_time: 505, status: 'EARLY' },
          { client_id: 5, client_name: 'Maroc Distribution', arrival_time: 535, departure_time: 550, status: 'OK' },
          { client_id: 6, client_name: 'Kenitra Fresh', arrival_time: 575, departure_time: 590, status: 'OK' },
        ],
        start_time: 480,
        end_time: 620,
        total_distance: 42.0,
        total_cost: 71.0,
      },
      {
        truck_id: 'Camion005',
        stops: [
          { client_id: 7, client_name: 'Casablanca Foods', arrival_time: 510, departure_time: 525, status: 'OK' },
        ],
        start_time: 480,
        end_time: 550,
        total_distance: 15.2,
        total_cost: 57.6,
      },
    ],
    unassigned: [],
    costs: {
      before: 450,
      after: 196.35,
      savings: 253.65,
      savings_percent: 56.4,
    },
    suggestions: [
      {
        type: 'UTILIZATION',
        severity: 'info',
        message: 'Camion005 sous-utilisé (1 arrêt)',
        action: 'Grouper avec Camion002 si possible',
      },
      {
        type: 'TIME_WINDOW',
        severity: 'warning',
        message: 'Royal Ceramics: arrivée 8:10, demande 10:00-12:00',
        action: 'Reporter ou modifier itinéraire',
      },
    ],
    metrics: {
      total_routes: 3,
      total_deliveries: 7,
      total_distance: 92.7,
      avg_utilization_percent: 65.3,
    },
  };

  function parseTimeToMinutes(timeString) {
    if (!timeString || typeof timeString !== 'string') return null;
    const cleaned = timeString.trim();
    const parts = cleaned.split(':').map((value) => Number(value));
    if (parts.length >= 2 && !Number.isNaN(parts[0]) && !Number.isNaN(parts[1])) {
      return parts[0] * 60 + parts[1];
    }
    const numeric = Number(cleaned);
    if (!Number.isNaN(numeric) && numeric >= 0 && numeric < 2400) {
      const hours = Math.floor(numeric / 100);
      const minutes = numeric % 100;
      return hours * 60 + minutes;
    }
    return null;
  }

  function getTotalPallets(planData) {
    if (!planData?.routes) return 0;
    return planData.routes.reduce((routeSum, route) => {
      const routeLoad = (route.load ?? route.stops?.reduce((sum, stop) => sum + (Number(stop.quantity) || 0), 0)) || 0;
      return routeSum + routeLoad;
    }, 0);
  }

  useEffect(() => {
    const loadPlan = async () => {
      try {
        const rows = await getDailyPlanningFromFile();
        const transports = Array.isArray(rows) ? rows : [];
        const selectedDayFromFile = transports.find((row) => row.delivery_day)?.delivery_day || 'Monday';
        setSelectedDay(selectedDayFromFile);
        const deliveriesForDay = transports
          .filter((row) => row.delivery_day === selectedDayFromFile)
          .filter((row) => row.status !== 'completed');

        const deliveries = deliveriesForDay.slice(0, 20).map((row, idx) => {
          const [lat, lng] = getClientPosition(row.end_location || row.start_location || row.client, idx);
          const earliest = parseTimeToMinutes(row.etd) ?? 480;
          const latest = parseTimeToMinutes(row.eta) ?? earliest + 540;
          const quantity = Number.isFinite(Number(row.quantity)) ? Math.max(1, Number(row.quantity)) : 1;
          return {
            id: Number(row.row_number || row.id || idx + 1),
            customer: row.client || row.end_location || `Delivery ${idx + 1}`,
            quantity,
            delivery_day: row.delivery_day || selectedDayFromFile,
            lat,
            lng,
            earliest_time: earliest,
            latest_time: latest,
          };
        });

        const availableTrucks = trucks
          .filter((t) => t.status !== 'En panne' && t.status !== 'En maintenance')
          .map((t) => ({
            id: t.id,
            type: t.type,
            capacity: Number.isFinite(Number(t.max_pallets)) ? Number(t.max_pallets) : Number(t.capacity),
          }));

        if (deliveries.length === 0) {
          console.warn('No deliveries available for planning on', selectedDay);
          setPlan(mockPlan);
          return;
        }

        const result = await generatePlanning({ deliveries, trucks: availableTrucks });
        setPlan(result);
      } catch (error) {
        console.error('Optimization error:', error);
        setPlan(mockPlan);
      } finally {
        setLoading(false);
      }
    };

    loadPlan();
  }, []);

  if (loading) {
    return (
      <div className="p-8 min-h-screen bg-[#f8f7f3]">
        <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-12 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[#7c3aed]/10 mb-4">
            <Sparkles size={24} className="text-[#7c3aed] animate-spin" />
          </div>
          <p className="font-semibold text-[#1a1a2e]">Generating optimal planning...</p>
          <p className="text-sm text-[#6b6b7b] mt-2">VRPTW with clustering, packing & time windows</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 min-h-screen bg-[#f8f7f3]">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <span className="inline-flex items-center gap-2 rounded-full bg-[#fef3c7] px-3 py-1 text-sm font-semibold text-[#b45309]">
            <Sparkles size={14} /> AI VRPTW Optimizer
          </span>
        </div>
        <h1 className="text-4xl font-bold text-[#1a1a2e]">Daily Delivery Planning</h1>
        <p className="mt-2 text-sm text-[#6b6b7b]">Complete VRPTW with geographic clustering, bin packing & time window adjustment</p>
        {selectedDay && (
          <p className="mt-2 text-sm text-[#6b6b7b]">Using deliveries for {selectedDay} from weekly planning</p>
        )}
        <p className="mt-3 text-xs text-[#52525b]">Excel position number is mapped to pallet count for capacity planning.</p>
      </motion.div>

      {/* Metrics & Savings */}
      <motion.div variants={container} initial="hidden" animate="show" className="grid gap-6 xl:grid-cols-6 mb-8">
        <motion.div variants={item} className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <Truck size={16} className="text-[#7c3aed]" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Routes</p>
          </div>
          <p className="text-3xl font-bold text-[#111827]">{plan.metrics.total_routes}</p>
          <p className="text-xs text-[#6b7280] mt-1">Optimized paths</p>
        </motion.div>

        <motion.div variants={item} className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <MapPin size={16} className="text-[#22c55e]" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Stops</p>
          </div>
          <p className="text-3xl font-bold text-[#111827]">{plan.metrics.total_deliveries}</p>
          <p className="text-xs text-[#6b7280] mt-1">Total deliveries</p>
        </motion.div>

        <motion.div variants={item} className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <Clock size={16} className="text-[#3b82f6]" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Distance</p>
          </div>
          <p className="text-3xl font-bold text-[#111827]">{plan.metrics.total_distance.toFixed(0)} km</p>
          <p className="text-xs text-[#6b7280] mt-1">Total mileage</p>
        </motion.div>

        <motion.div variants={item} className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle size={16} className="text-[#f97316]" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Utilization</p>
          </div>
          <p className="text-3xl font-bold text-[#111827]">{((plan.metrics.avg_utilization_percent ?? plan.metrics.avg_utilization ?? 0)).toFixed(0)}%</p>
          <p className="text-xs text-[#6b7280] mt-1">Avg capacity used</p>
        </motion.div>

        <motion.div variants={item} className="rounded-[1.75rem] bg-gradient-to-br from-[#dcfce7] to-[#ecfdf5] p-6 border border-[#22c55e] shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown size={16} className="text-[#22c55e]" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#16a34a]">Savings</p>
          </div>
          <p className="text-3xl font-bold text-[#16a34a]">{((plan.costs?.savings_percent ?? 0)).toFixed(0)}%</p>
          <p className="text-xs text-[#16a34a] mt-1">{((plan.costs?.savings ?? 0)).toFixed(0)}€ saved</p>
        </motion.div>

        <motion.div variants={item} className="rounded-[1.75rem] bg-white p-6 border border-[#e8e5eb] shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <MapPin size={16} className="text-[#f59e0b]" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#6b7280]">Pallets</p>
          </div>
          <p className="text-3xl font-bold text-[#111827]">{getTotalPallets(plan)}</p>
          <p className="text-xs text-[#6b7280] mt-1">Total pallets scheduled</p>
        </motion.div>
      </motion.div>

      {/* Cost Comparison */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="rounded-[2rem] bg-white p-6 border border-[#e8e5eb] shadow-sm mb-8"
      >
        <h2 className="text-lg font-semibold text-[#1a1a2e] mb-4">Cost Comparison</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-[#6b7280] mb-2">Before optimization</p>
            <p className="text-3xl font-bold text-[#dc2626]">{plan.costs.before.toFixed(0)}€</p>
          </div>
          <div className="flex items-center justify-center">
            <div className="text-center">
              <TrendingDown size={32} className="text-[#22c55e] mx-auto mb-2" />
              <p className="text-sm font-semibold text-[#22c55e]">{plan.costs.savings_percent}%</p>
            </div>
          </div>
          <div>
            <p className="text-sm text-[#6b7280] mb-2">After optimization</p>
            <p className="text-3xl font-bold text-[#22c55e]">{plan.costs.after.toFixed(2)}€</p>
          </div>
        </div>
      </motion.div>

      {/* Routes Timeline */}
      <div className="space-y-6">
        {plan.routes.map((route, routeIdx) => (
          <motion.div
            key={routeIdx}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 + routeIdx * 0.1 }}
            className="rounded-[2rem] bg-white border border-[#e8e5eb] shadow-sm overflow-hidden"
          >
            {/* Route Header */}
            <div
              onClick={() => setExpandedRoute(expandedRoute === routeIdx ? -1 : routeIdx)}
              className="p-6 bg-gradient-to-r from-[#f0ede8] to-[#f8f7f3] border-b border-[#e8e5eb] cursor-pointer hover:from-[#e8e5df] transition"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-[#7c3aed] flex items-center justify-center text-white font-bold">
                    {routeIdx + 1}
                  </div>
                  <div>
                    <h3 className="font-semibold text-[#1a1a2e]">{route.truck_id}</h3>
                    <p className="text-sm text-[#6b6b7b]">
                      {formatTime(route.start_time)} - {formatTime(route.end_time)} • {route.stops.length} stops • {route.total_distance.toFixed(1)}km
                    </p>
                    <p className="text-xs text-[#6b6b7b] mt-1">
                      Capacité max: {route.capacity ?? 'N/A'} palettes • Charge: {route.load ?? route.stops.reduce((sum, stop) => sum + (stop.quantity ?? 0), 0)} palettes
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-[#1a1a2e]">{route.total_cost.toFixed(2)}€</p>
                  <p className="text-xs text-[#6b6b7b]">Total cost</p>
                </div>
              </div>
            </div>

            {/* Route Details (Timeline) */}
            {expandedRoute === routeIdx && (
              <div className="p-6 space-y-4">
                {/* Start */}
                <div className="flex gap-4">
                  <div className="w-20 text-right">
                    <p className="font-semibold text-[#7c3aed]">{formatTime(route.start_time)}</p>
                  </div>
                  <div className="flex-1">
                    <div className="rounded-xl bg-[#f5f3ff] border border-[#7c3aed] p-3">
                      <p className="font-semibold text-[#4c1d95]">🚐 Departure from depot</p>
                    </div>
                  </div>
                </div>

                {/* Timeline connector */}
                <div className="flex gap-4">
                  <div className="w-20 flex justify-center">
                    <div className="w-0.5 h-8 bg-gradient-to-b from-[#7c3aed] to-[#e5e7eb]" />
                  </div>
                </div>

                {/* Stops */}
                {route.stops.map((stop, stopIdx) => (
                  <div key={stopIdx}>
                    <div className="flex gap-4">
                      <div className="w-20 text-right">
                        <p className="font-semibold text-[#1a1a2e]">{formatTime(stop.arrival_time)}</p>
                        <p className="text-xs text-[#6b6b7b]">→ {formatTime(stop.departure_time)}</p>
                      </div>
                      <div className="flex-1">
                        <div className={`rounded-xl p-4 border ${
                          stop.status === 'OK' ? 'bg-[#f0fdf4] border-[#22c55e]' :
                          stop.status === 'EARLY' ? 'bg-[#fef3c7] border-[#f97316]' :
                          'bg-[#fee2e2] border-[#dc2626]'
                        }`}>
                          <div className="flex items-start justify-between mb-2">
                            <div>
                              <p className="font-semibold text-[#1a1a2e]">📍 {stop.client_name}</p>
                              <p className="text-xs text-[#6b6b7b] mt-1">Client ID: {stop.client_id}</p>
                              <p className="text-xs text-[#6b6b7b] mt-1">Palettes: {stop.quantity ?? 0}</p>
                            </div>
                            <span className={`text-xs font-semibold px-2 py-1 rounded ${
                              stop.status === 'OK' ? 'bg-[#dcfce7] text-[#16a34a]' :
                              stop.status === 'EARLY' ? 'bg-[#fcd34d] text-[#b45309]' :
                              'bg-[#fecaca] text-[#991b1b]'
                            }`}>
                              {stop.status}
                            </span>
                          </div>
                          {stop.status === 'EARLY' && (
                            <p className="text-xs text-[#b45309] mt-2">⚠️ Early arrival - wait for time window</p>
                          )}
                          {stop.status === 'LATE' && (
                            <p className="text-xs text-[#dc2626] mt-2">❌ Late delivery - outside time window</p>
                          )}
                        </div>
                      </div>
                    </div>
                    {stopIdx < route.stops.length - 1 && (
                      <div className="flex gap-4 mt-4">
                        <div className="w-20 flex justify-center">
                          <div className="w-0.5 h-8 bg-gradient-to-b from-[#e5e7eb] to-[#e5e7eb]" />
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {/* Return to depot */}
                <div className="flex gap-4 mt-4">
                  <div className="w-20 flex justify-center">
                    <div className="w-0.5 h-8 bg-gradient-to-b from-[#e5e7eb] to-[#7c3aed]" />
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="w-20 text-right">
                    <p className="font-semibold text-[#7c3aed]">{formatTime(route.end_time)}</p>
                  </div>
                  <div className="flex-1">
                    <div className="rounded-xl bg-[#f5f3ff] border border-[#7c3aed] p-3">
                      <p className="font-semibold text-[#4c1d95]">🏢 Return to depot</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        ))}
      </div>

      {/* Suggestions */}
      {plan.suggestions && plan.suggestions.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="rounded-[2rem] bg-white p-6 border border-[#e8e5eb] shadow-sm mt-8"
        >
          <h2 className="text-lg font-semibold text-[#1a1a2e] mb-4">Recommendations</h2>
          <div className="space-y-3">
            {plan.suggestions.map((sug, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-xl border ${
                  sug.severity === 'high' ? 'bg-[#fee2e2] border-[#dc2626]' :
                  sug.severity === 'warning' ? 'bg-[#fef3c7] border-[#f97316]' :
                  'bg-[#dbeafe] border-[#3b82f6]'
                }`}
              >
                <div className="flex gap-3">
                  <AlertCircle size={18} className={sug.severity === 'high' ? 'text-[#dc2626]' : sug.severity === 'warning' ? 'text-[#f97316]' : 'text-[#3b82f6]'} />
                  <div className="flex-1">
                    <p className="font-semibold text-[#1a1a2e]">{sug.message}</p>
                    <p className="text-sm text-[#6b6b7b] mt-1">💡 {sug.action}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
