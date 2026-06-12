"use client";

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { motion } from 'framer-motion';
import { Users, MapPin, Activity, Map } from 'lucide-react';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';
import { clients as initialClients, drivers, trucks, getClientPosition } from '../../data/coficabData';
import { palette } from '@/lib/theme';

const ClientMap = dynamic(() => import('../../components/map/ClientMap'), { ssr: false });

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: 'easeOut' } },
};

export default function ClientsPage() {
  const [clients, setClients] = useState(
    initialClients.map((client, index) => ({
      ...client,
      ...(() => {
        const [lat, lng] = getClientPosition(client.destination, index);
        return { lat, lng };
      })(),
    }))
  );
  const [selectedClient, setSelectedClient] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newClient, setNewClient] = useState({ customer: '', destination: '', km: '' });
  const [chatMessages, setChatMessages] = useState([
    'Clients page loaded. Select a row to inspect customer delivery details.',
  ]);

  const clientSummary = useMemo(
    () => {
      const locations = { nord: 0, sud: 0, centre: 0 };
      
      // Catégoriser les clients par région basée sur la latitude
      clients.forEach(client => {
        const [lat] = getClientPosition(client.destination, 0);
        if (lat > 36.5) locations.nord++;
        else if (lat < 35.5) locations.sud++;
        else locations.centre++;
      });

      // Calculer les clients actifs (2/3 de la liste)
      const activeCount = Math.floor(clients.length * 0.67);

      return {
        total: clients.length,
        averageKm: clients.length ? (clients.reduce((sum, client) => sum + client.km, 0) / clients.length).toFixed(1) : 0,
        activeClients: activeCount,
        activePercent: clients.length ? Math.round((activeCount / clients.length) * 100) : 0,
        locations,
        mainLocation: Object.entries(locations).sort(([,a], [,b]) => b - a)[0][0],
      };
    },
    [clients]
  );

  const onAddClient = (event) => {
    event.preventDefault();
    if (!newClient.customer || !newClient.destination || !newClient.km) {
      setChatMessages((prev) => ['Please fill all fields before adding a client.', ...prev]);
      return;
    }

    const next = {
      id: `client-${Date.now()}`,
      customer: newClient.customer,
      destination: newClient.destination,
      km: Number(newClient.km),
      ...(() => {
        const [lat, lng] = getClientPosition(newClient.destination, clients.length);
        return { lat, lng };
      })(),
    };

    setClients((prev) => [next, ...prev]);
    setNewClient({ customer: '', destination: '', km: '' });
    setShowAddForm(false);
    setSelectedClient(next);
    setChatMessages((prev) => ['New client added to the COFICAB roster.', ...prev]);
  };

  return (
    <div className="p-8 min-h-screen bg-canvas">
      {/* En-tête avec titre et statistiques */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-6 xl:flex-row xl:items-center xl:justify-between mb-8"
      >
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-brand-600">Client Management</p>
          <h1 className="mt-3 text-4xl font-bold text-ink">Good morning, Ghada</h1>
          <p className="mt-2 text-sm text-muted">Overview of customer network, delivery routes and distances.</p>
        </div>
      </motion.div>

      {/* Cartes KPI principales */}
      <motion.div variants={container} initial="hidden" animate="show" className="grid gap-6 xl:grid-cols-4 mb-8">
        <motion.div
          variants={item}
          whileHover={{ y: -3, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
          className="bg-white rounded-2xl p-6 border border-border cursor-pointer transition-shadow"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-brand-50">
              <Users size={20} color={palette.brand[600]} />
            </div>
          </div>
          <p className="text-sm text-muted mb-1">Total Clients</p>
          <p className="text-4xl font-bold text-ink mb-3">{clientSummary.total}</p>
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-[#22c55e]">✓ 100%</span>
            <span className="text-xs text-[#9e9aa4]">active</span>
          </div>
        </motion.div>

        <motion.div
          variants={item}
          whileHover={{ y: -3, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
          className="bg-white rounded-2xl p-6 border border-border cursor-pointer transition-shadow"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-[#fef3c7]">
              <MapPin size={20} color="#f97316" />
            </div>
          </div>
          <p className="text-sm text-muted mb-1">Avg. Distance</p>
          <p className="text-4xl font-bold text-ink mb-3">{clientSummary.averageKm} km</p>
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-[#f97316]">→ per route</span>
          </div>
        </motion.div>

        <motion.div
          variants={item}
          whileHover={{ y: -3, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
          className="bg-white rounded-2xl p-6 border border-border cursor-pointer transition-shadow"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-[#dbeafe]">
              <Activity size={20} color="#3b82f6" />
            </div>
          </div>
          <p className="text-sm text-muted mb-1">Clients actifs</p>
          <p className="text-4xl font-bold text-ink mb-3">{clientSummary.activeClients}</p>
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-[#3b82f6]">{clientSummary.activePercent}%</span>
            <span className="text-xs text-[#9e9aa4]">en livraison</span>
          </div>
        </motion.div>

        <motion.div
          variants={item}
          whileHover={{ y: -3, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
          className="bg-white rounded-2xl p-6 border border-border cursor-pointer transition-shadow"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-[#f0fdf4]">
              <Map size={20} color="#22c55e" />
            </div>
          </div>
          <p className="text-sm text-muted mb-1">Localisation</p>
          <p className="text-4xl font-bold text-ink mb-3">{clientSummary.locations.nord + clientSummary.locations.sud}</p>
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium text-[#22c55e] capitalize">{clientSummary.mainLocation} dominante</span>
          </div>
        </motion.div>
      </motion.div>

      {/* Section principale */}
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="space-y-6"
        >
          {/* Clients Table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="rounded-2xl bg-white p-6 border border-border transition-shadow hover:shadow-lg"
          >
<div className="mb-6 flex items-center justify-between">
              <div>
                <p className="text-sm text-muted">Customer network</p>
                <h2 className="text-2xl font-semibold text-ink">COFICAB clients and delivery routes</h2>
              </div>
              <button
                type="button"
                onClick={() => setShowAddForm((prev) => !prev)}
                className="text-sm font-semibold text-brand-600 hover:text-brand-800 transition"
              >
                {showAddForm ? '✕ Cancel' : '+ Add client'}
              </button>
            </div>

            {showAddForm && (
              <form onSubmit={onAddClient} className="mb-6 grid gap-4 rounded-[1.5rem] border border-border bg-white p-5">
                <div className="grid gap-4 sm:grid-cols-3">
                  <label className="space-y-2 text-sm text-ink">
                    <span>Customer</span>
                    <input
                      value={newClient.customer}
                      onChange={(event) => setNewClient({ ...newClient, customer: event.target.value })}
                      className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition"
                    />
                  </label>
                  <label className="space-y-2 text-sm text-ink">
                    <span>Destination</span>
                    <input
                      value={newClient.destination}
                      onChange={(event) => setNewClient({ ...newClient, destination: event.target.value })}
                      className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition"
                    />
                  </label>
                  <label className="space-y-2 text-sm text-ink">
                    <span>Distance (km)</span>
                    <input
                      type="number"
                      step="0.1"
                      value={newClient.km}
                      onChange={(event) => setNewClient({ ...newClient, km: event.target.value })}
                      className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-600 focus:ring-offset-0 transition"
                    />
                  </label>
                </div>
                <button type="submit" className="w-full rounded-xl bg-brand-600 px-5 py-2 text-sm font-semibold text-white hover:bg-brand-700 transition">
                  Save client
                </button>
              </form>
            )}

            <div className="overflow-hidden rounded-[1.5rem] border border-border">
              <div className="grid grid-cols-[1.3fr_1fr_0.8fr_0.9fr] gap-4 bg-canvas px-6 py-4 text-sm font-semibold uppercase tracking-[0.15em] text-muted">
                <span>Customer</span>
                <span>Destination</span>
                <span>Distance</span>
                <span>Action</span>
              </div>
              <div className="divide-y divide-border bg-white max-h-96 overflow-y-auto">
                {clients.map((client) => (
                  <motion.div
                    key={client.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="grid grid-cols-[1.3fr_1fr_0.8fr_0.9fr] gap-4 px-6 py-4 items-center text-sm text-ink hover:bg-canvas transition cursor-pointer"
                    onClick={() => setSelectedClient(client)}
                  >
                    <div>
                      <p className="font-semibold">{client.customer}</p>
                    </div>
                    <span className="text-muted">{client.destination}</span>
                    <span className="inline-block bg-[#fef3c7] text-[#f97316] rounded-xl px-3 py-1 text-xs font-semibold">{client.km} km</span>
                    <button type="button" className="rounded-xl border border-border bg-white px-3 py-2 text-xs font-semibold text-brand-600 hover:bg-canvas transition">
                      Details
                    </button>
                  </motion.div>
                ))}
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Sidebar */}
        <motion.aside
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="space-y-6"
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.35 }}
            className="rounded-2xl bg-white p-6 border border-border transition-shadow hover:shadow-lg"
          >
            <h2 className="text-lg font-semibold text-ink">Client Map</h2>
            <p className="mt-2 text-sm text-muted">All active destinations displayed on the delivery map.</p>
            <div className="mt-4">
              <ClientMap clients={clients.slice(0, 22)} />
            </div>
          </motion.div>

          {selectedClient && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.4 }}
              className="rounded-2xl bg-white p-6 border border-border transition-shadow hover:shadow-lg"
            >
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted">Selected Client</p>
                  <h2 className="text-lg font-semibold text-ink">{selectedClient.customer}</h2>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedClient(null)}
                  className="rounded-xl bg-[#f0f0f5] px-3 py-2 text-xs font-semibold text-ink hover:bg-[#e5e7eb]"
                >
                  Close
                </button>
              </div>
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-muted">Destination:</p>
                  <p className="font-semibold text-ink">{selectedClient.destination}</p>
                </div>
                <div>
                  <p className="text-muted">Distance:</p>
                  <p className="font-semibold text-ink">{selectedClient.km} km</p>
                </div>
              </div>
            </motion.div>
          )}

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.45 }}
            className="rounded-2xl bg-white p-6 border border-border transition-shadow hover:shadow-lg"
          >
            <p className="text-sm text-muted">Message Feed</p>
            <h2 className="text-lg font-semibold text-ink">Activity</h2>
            <div className="mt-4">
              <ChatPanel
                messages={chatMessages}
                title="Clients Copilot"
                context={{ page: 'clients', clientCount: clients.length, clients, selectedClient }}
              />
            </div>
          </motion.div>
        </motion.aside>
      </div>
    </div>
  );
}
