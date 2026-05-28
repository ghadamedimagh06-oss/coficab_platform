import { useState } from 'react';
import { X } from 'lucide-react';

export default function AddDeliveryModal({ open, trucks, onClose, onAdd }) {
  const [form, setForm] = useState({
    client: '',
    quantity_positions: '1',
    quantity_kg: '0',
    etd: '08:00',
    eta: '09:00',
    priority: 'normal',
    truck_id: trucks?.[0]?.truck_id || 1,
  });

  if (!open) return null;

  const update = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 px-4">
      <div className="w-full max-w-lg rounded-[2rem] border border-[#e8e5df] bg-white p-6 shadow-xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[#1a1a2e]">Add delivery</h2>
          <button type="button" onClick={onClose} className="rounded-full p-2 text-[#6b6b7b] hover:bg-[#f8f7f3]">
            <X size={18} />
          </button>
        </div>
        <div className="grid gap-4">
          <label className="text-sm font-medium text-[#1a1a2e]">
            Client
            <input className="mt-2 w-full rounded-2xl border border-[#e8e5df] px-4 py-3 outline-none focus:border-[#7c3aed]" value={form.client} onChange={(e) => update('client', e.target.value)} />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-sm font-medium text-[#1a1a2e]">
              Positions
              <input type="number" min="1" className="mt-2 w-full rounded-2xl border border-[#e8e5df] px-4 py-3 outline-none focus:border-[#7c3aed]" value={form.quantity_positions} onChange={(e) => update('quantity_positions', e.target.value)} />
            </label>
            <label className="text-sm font-medium text-[#1a1a2e]">
              Truck
              <select className="mt-2 w-full rounded-2xl border border-[#e8e5df] px-4 py-3 outline-none focus:border-[#7c3aed]" value={form.truck_id} onChange={(e) => update('truck_id', Number(e.target.value))}>
                {trucks.map((truck) => <option key={truck.truck_id} value={truck.truck_id}>{truck.truck_label}</option>)}
              </select>
            </label>
          </div>
          <div className="grid gap-4 sm:grid-cols-4">
            <label className="text-sm font-medium text-[#1a1a2e]">
              Gross kg
              <input type="number" min="0" className="mt-2 w-full rounded-2xl border border-[#e8e5df] px-4 py-3 outline-none focus:border-[#7c3aed]" value={form.quantity_kg} onChange={(e) => update('quantity_kg', e.target.value)} />
            </label>
            <label className="text-sm font-medium text-[#1a1a2e]">
              ETD
              <input type="time" className="mt-2 w-full rounded-2xl border border-[#e8e5df] px-4 py-3 outline-none focus:border-[#7c3aed]" value={form.etd} onChange={(e) => update('etd', e.target.value)} />
            </label>
            <label className="text-sm font-medium text-[#1a1a2e]">
              ETA
              <input type="time" className="mt-2 w-full rounded-2xl border border-[#e8e5df] px-4 py-3 outline-none focus:border-[#7c3aed]" value={form.eta} onChange={(e) => update('eta', e.target.value)} />
            </label>
            <label className="text-sm font-medium text-[#1a1a2e]">
              Priority
              <select className="mt-2 w-full rounded-2xl border border-[#e8e5df] px-4 py-3 outline-none focus:border-[#7c3aed]" value={form.priority} onChange={(e) => update('priority', e.target.value)}>
                <option value="urgent">Urgent</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
            </label>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-full border border-[#e8e5df] px-5 py-2 text-sm font-semibold text-[#1a1a2e]">Cancel</button>
          <button
            type="button"
            onClick={() => {
              onAdd({
                ...form,
                quantity_positions: Math.max(1, Number(form.quantity_positions) || 1),
                quantity_kg: Math.max(0, Number(form.quantity_kg) || 0),
              });
              onClose();
            }}
            className="rounded-full bg-[#7c3aed] px-5 py-2 text-sm font-semibold text-white"
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
