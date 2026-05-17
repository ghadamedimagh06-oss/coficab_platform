"use client";

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { getTransports } from '../../services/api';
import ChatPanel from '../../../components/chat/ChatPanel';

export default function TransportDetailPage() {
  const params = useParams();
  const { id } = params || {};
  const [transport, setTransport] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);

  useEffect(() => {
    async function loadTransport() {
      try {
        const list = await getTransports();
        const found = (Array.isArray(list) ? list : []).find((item) => String(item.id) === String(id));
        setTransport(found || null);
        setChatMessages((prev) => [`Transport details loaded for ID ${id}.`, ...prev]);
      } catch (error) {
        setChatMessages((prev) => ['Unable to load transport detail. Check backend connectivity.', ...prev]);
      }
    }
    loadTransport();
  }, [id]);

  if (!transport) {
    return (
      <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-8 shadow-xl shadow-black/20">
        <p className="text-slate-400">Transport not found or still loading. Confirm the ID exists in the backend transport dataset.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-8 xl:grid-cols-[1.35fr_0.85fr]">
      <section className="space-y-6">
        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-8 shadow-xl shadow-black/20">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-slate-400">Transport detail</p>
              <h2 className="text-3xl font-semibold">{transport.vehicle || `Transport ${transport.id}`}</h2>
            </div>
            <span className="rounded-full bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200">{transport.status || 'On time'}</span>
          </div>

          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-6">
              <p className="text-sm text-slate-400">Driver</p>
              <p className="mt-3 text-xl font-semibold">{transport.driver || 'Unknown'}</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-6">
              <p className="text-sm text-slate-400">Distance</p>
              <p className="mt-3 text-xl font-semibold">{transport.distance_km ?? 'N/A'} km</p>
            </div>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-6">
              <p className="text-sm text-slate-400">Route start</p>
              <p className="mt-3 text-lg font-semibold">{transport.start_location || 'Unknown'}</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-6">
              <p className="text-sm text-slate-400">Route end</p>
              <p className="mt-3 text-lg font-semibold">{transport.end_location || 'Unknown'}</p>
            </div>
          </div>

          <div className="mt-8 rounded-3xl border border-slate-800 bg-slate-950/80 p-6">
            <p className="text-sm text-slate-400">Route history</p>
            <ul className="mt-4 space-y-3 text-sm text-slate-300">
              <li>2026-05-04 10:12 - Route created by planner</li>
              <li>2026-05-04 12:26 - ETA updated by AI system</li>
              <li>2026-05-04 14:05 - Delay risk flagged</li>
            </ul>
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <h2 className="text-xl font-semibold">Timeline & logs</h2>
          <p className="mt-3 text-sm text-slate-400">This detail view shows route history, decision timestamps, and audit actions for the selected transport.</p>
        </div>

        <ChatPanel messages={chatMessages} />
      </aside>
    </div>
  );
}
