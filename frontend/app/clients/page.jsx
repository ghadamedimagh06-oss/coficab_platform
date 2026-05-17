"use client";

import { useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';
import IconBubble from '../../components/icons/IconBubble';
import { clients as initialClients, drivers, trucks, getClientPosition } from '../../data/coficabData';

const ClientMap = dynamic(() => import('../../components/map/ClientMap'), { ssr: false });

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
    () => ({
      total: clients.length,
      averageKm: clients.length ? (clients.reduce((sum, client) => sum + client.km, 0) / clients.length).toFixed(1) : 0,
    }),
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
    <div className="grid gap-8 xl:grid-cols-[1.35fr_0.85fr]">
      <section className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-3">
          <StatCard title="Clients" value={clientSummary.total} hint="Total customer stops" icon={<IconBubble kind="box" />} />
          <StatCard title="Fleet" value={trucks.length} hint="Active trucks" icon={<IconBubble kind="truck" />} />
          <StatCard title="Drivers" value={drivers.length} hint="Assigned operators" icon={<IconBubble kind="user" />} />
        </div>

        <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
          <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-[#6b6b7b]">Customer network</p>
              <h2 className="text-2xl font-semibold text-[#1a1a2e]">COFICAB clients and delivery routes</h2>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setShowAddForm((prev) => !prev)}
                className="rounded-full bg-[#7c3aed] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#6d28d9]"
              >
                {showAddForm ? 'Cancel' : 'Add client'}
              </button>
            </div>
          </div>

          {showAddForm && (
            <form onSubmit={onAddClient} className="mb-6 grid gap-4 rounded-[1.5rem] border border-[#e8e5df] bg-white p-5 shadow-sm">
              <div className="grid gap-4 sm:grid-cols-3">
                <label className="space-y-2 text-sm text-[#1a1a2e]">
                  <span>Customer</span>
                  <input
                    value={newClient.customer}
                    onChange={(event) => setNewClient({ ...newClient, customer: event.target.value })}
                    className="w-full rounded-3xl border border-[#e8e5df] bg-[#faf8f5] px-4 py-3 text-sm text-[#1a1a2e] outline-none"
                  />
                </label>
                <label className="space-y-2 text-sm text-[#1a1a2e]">
                  <span>Destination</span>
                  <input
                    value={newClient.destination}
                    onChange={(event) => setNewClient({ ...newClient, destination: event.target.value })}
                    className="w-full rounded-3xl border border-[#e8e5df] bg-[#faf8f5] px-4 py-3 text-sm text-[#1a1a2e] outline-none"
                  />
                </label>
                <label className="space-y-2 text-sm text-[#1a1a2e]">
                  <span>Distance (km)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={newClient.km}
                    onChange={(event) => setNewClient({ ...newClient, km: event.target.value })}
                    className="w-full rounded-3xl border border-[#e8e5df] bg-[#faf8f5] px-4 py-3 text-sm text-[#1a1a2e] outline-none"
                  />
                </label>
              </div>
              <button type="submit" className="w-full rounded-full bg-[#7c3aed] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#6d28d9]">
                Save client
              </button>
            </form>
          )}

          <div className="overflow-hidden rounded-[1.5rem] border border-[#e8e5df] bg-white text-sm text-[#1a1a2e]">
            <div className="grid grid-cols-[1.3fr_1fr_0.8fr_0.9fr] gap-4 px-6 py-4 uppercase tracking-[0.18em] text-[#6b6b7b]">
              <span>Customer</span>
              <span>Destination</span>
              <span>Distance</span>
              <span>Action</span>
            </div>
            <div className="divide-y divide-[#e8e5df]">
              {clients.map((client) => (
                <div key={client.id} className="grid grid-cols-[1.3fr_1fr_0.8fr_0.9fr] gap-4 px-6 py-4 hover:bg-[#faf8f5] transition cursor-pointer" onClick={() => setSelectedClient(client)}>
                  <span className="font-semibold text-[#1a1a2e]">{client.customer}</span>
                  <span className="text-[#6b6b7b]">{client.destination}</span>
                  <span className="text-[#6b6b7b]">{client.km} km</span>
                  <button type="button" className="rounded-3xl border border-[#e8e5df] bg-white px-4 py-2 text-sm text-[#1a1a2e] hover:bg-[#faf8f5]">
                    Details
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-[#1a1a2e]">Client map</h2>
          <p className="mt-3 text-sm text-[#6b6b7b]">All active client destinations are displayed on the COFICAB delivery map.</p>
          <div className="mt-6">
            <ClientMap clients={clients.slice(0, 22)} />
          </div>
        </div>

        <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="text-sm text-[#6b6b7b]">Driver roster</p>
              <h2 className="text-xl font-semibold text-[#1a1a2e]">Active drivers</h2>
            </div>
          </div>
          <div className="space-y-4">
            {drivers.map((driver) => (
              <div key={driver.id} className="rounded-3xl border border-[#e8e5df] bg-[#faf8f5] p-4 text-[#1a1a2e]">
                <div className="flex items-center gap-4">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[#7c3aed] text-lg font-semibold text-white">
                    {driver.full_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <p className="font-semibold">{driver.full_name}</p>
                    <p className="text-sm text-[#6b6b7b]">{driver.phone}</p>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-[#6b6b7b]">
                  <div>
                    <p className="font-semibold text-[#1a1a2e]">License</p>
                    <p>{driver.license_number} / {driver.license_type}</p>
                  </div>
                  <div>
                    <p className="font-semibold text-[#1a1a2e]">Truck</p>
                    <p>{driver.assigned_truck || 'Unassigned'}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-[#1a1a2e]">Truck fleet</h2>
          <div className="mt-4 grid gap-3">
            {trucks.map((truck) => (
              <div key={truck.id} className="rounded-3xl border border-[#e8e5df] bg-[#faf8f5] p-4 text-[#1a1a2e]">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-semibold">{truck.id}</p>
                    <p className="text-sm text-[#6b6b7b]">{truck.plate_number}</p>
                  </div>
                  <span className="rounded-full bg-[#f0f0f5] px-3 py-1 text-xs font-semibold uppercase text-[#1a1a2e]">{truck.type}</span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-[#6b6b7b]">
                  <div>
                    <p className="font-semibold text-[#1a1a2e]">Capacity</p>
                    <p>{truck.capacity} kg</p>
                  </div>
                  <div>
                    <p className="font-semibold text-[#1a1a2e]">Pallets</p>
                    <p>{truck.max_pallets}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {selectedClient && (
          <div className="rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-[#6b6b7b]">Selected client</p>
                <h2 className="text-xl font-semibold text-[#1a1a2e]">{selectedClient.customer}</h2>
              </div>
              <button
                type="button"
                onClick={() => setSelectedClient(null)}
                className="rounded-full bg-[#f0f0f5] px-4 py-2 text-sm font-semibold text-[#1a1a2e] hover:bg-[#e5e7eb]"
              >
                Close
              </button>
            </div>
            <div className="space-y-3 text-sm text-[#6b6b7b]">
              <p><span className="font-semibold text-[#1a1a2e]">Destination:</span> {selectedClient.destination}</p>
              <p><span className="font-semibold text-[#1a1a2e]">Distance:</span> {selectedClient.km} km</p>
              <p><span className="font-semibold text-[#1a1a2e]">Note:</span> Customer delivery details are available for route planning and dispatch.</p>
            </div>
          </div>
        )}
      </aside>

      <div className="xl:col-span-2">
        <ChatPanel messages={chatMessages} />
      </div>
    </div>
  );
}
