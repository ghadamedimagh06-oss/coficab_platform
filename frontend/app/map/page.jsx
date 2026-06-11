"use client";

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { getLiveTracking } from '../services/api';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';
import { clients as initialClients, getClientPosition } from '../../data/coficabData';

const TruckMap = dynamic(() => import('../../components/map/TruckMap'), { ssr: false });

const fallbackMapClients = initialClients.map((client, index) => {
  const [lat, lng] = getClientPosition(client.destination, index);
  return { ...client, lat, lng };
});

export default function MapPage() {
  const [tracking, setTracking] = useState([]);
  const [mapClients, setMapClients] = useState(fallbackMapClients);
  const [chatMessages, setChatMessages] = useState([]);

  useEffect(() => {
    async function loadTracking() {
      try {
        const live = await getLiveTracking();
        const items = live?.tracking_data ? Object.values(live.tracking_data) : live || [];
        setTracking(items);
        if (Array.isArray(live?.clients) && live.clients.length) {
          setMapClients(live.clients);
        }
        setChatMessages((prev) => [
          'Real-time truck positions refreshed. Click a marker for ETA and status details.',
          ...prev,
        ]);
      } catch (error) {
        setChatMessages((prev) => ['Unable to refresh map data. Check backend polling settings.', ...prev]);
      }
    }
    loadTracking();
  }, []);

  const statusCounts = tracking.reduce(
    (acc, item) => {
      const status = item.status?.toLowerCase();
      if (status?.includes('critical')) acc.critical += 1;
      else if (status?.includes('delay')) acc.warning += 1;
      else acc.onTime += 1;
      return acc;
    },
    { onTime: 0, warning: 0, critical: 0 }
  );

  return (
    <div className="min-h-screen bg-[#f8f7f3] p-8">
      <div className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Live Tracking</p>
        <h1 className="mt-3 text-3xl font-semibold text-[#1a1a2e]">Delivery network map</h1>
        <p className="mt-2 text-sm text-[#6b6b7b]">Client destinations across Tunisia, the COFICAB depot, and any trucks reporting a live position.</p>
      </div>

      <div className="grid gap-8 xl:grid-cols-[1.5fr_0.9fr]">
        <section className="space-y-6">
          <div className="grid gap-6 sm:grid-cols-3">
            <StatCard title="Total trucks" value={tracking.length} hint="Active vehicles in the fleet" icon={<IconBubble kind="truck" />} />
            <StatCard title="On time" value={statusCounts.onTime} hint="Healthy routes" icon={<IconBubble kind="chart" />} />
            <StatCard title="Critical delays" value={statusCounts.critical} hint="Requires intervention" icon={<IconBubble kind="bolt" />} />
          </div>

          <TruckMap trucks={tracking} clients={mapClients} />

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <p className="text-sm uppercase tracking-[0.18em] text-[#6b6b7b]">Route stability</p>
              <p className="mt-3 text-3xl font-semibold text-[#7c3aed]">{tracking.length ? ((statusCounts.onTime / tracking.length) * 100).toFixed(0) : 0}%</p>
            </div>
            <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <p className="text-sm uppercase tracking-[0.18em] text-[#6b6b7b]">Delay risk</p>
              <p className="mt-3 text-3xl font-semibold text-[#d97706]">{statusCounts.warning}</p>
            </div>
            <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <p className="text-sm uppercase tracking-[0.18em] text-[#6b6b7b]">Critical alerts</p>
              <p className="mt-3 text-3xl font-semibold text-[#ef4444]">{statusCounts.critical}</p>
            </div>
          </div>
        </section>

        <aside className="space-y-6">
          <div className="rounded-[1.75rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-[#1a1a2e]">Map insights</h2>
            <p className="mt-3 text-sm text-[#6b6b7b]">Blue dots are client delivery destinations, gold is the COFICAB Mégrine depot, and coloured dots are trucks reporting a live GPS position. Foreign export sites are kept off this Tunisia view.</p>
          </div>

          <ChatPanel messages={chatMessages} />
        </aside>
      </div>
    </div>
  );
}
