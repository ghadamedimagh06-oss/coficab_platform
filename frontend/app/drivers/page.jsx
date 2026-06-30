"use client";

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Users, Clock3, CheckCircle, Plus, X } from 'lucide-react';
import { createFleetDriver, getFleetDrivers, getFleetTrucks } from '../services/api';

const EMPTY_FORM = {
  full_name: '',
  phone: '',
  permis_type: 'C',
  permis_numero: '',
  status: 'ACTIF',
  camion_defaut_id: '',
  shift_start: '08:00',
  shift_end: '17:00',
};

export default function DriversPage() {
  const [drivers, setDrivers] = useState([]);
  const [trucks, setTrucks] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  async function loadRoster() {
    const [driverRows, truckRows] = await Promise.all([getFleetDrivers(), getFleetTrucks()]);
    setDrivers(Array.isArray(driverRows) ? driverRows : []);
    setTrucks(Array.isArray(truckRows) ? truckRows : []);
  }

  useEffect(() => {
    loadRoster().catch((err) => setError(err.message || 'Unable to load drivers'));
  }, []);

  const truckLabels = useMemo(
    () => Object.fromEntries(trucks.map((truck) => [truck.id, truck.plate_number])),
    [trucks],
  );
  const summary = {
    total: drivers.length,
    active: drivers.filter((driver) => driver.status === 'ACTIF').length,
    nightShift: drivers.filter((driver) => driver.shift_start && driver.shift_start >= '18:00').length,
  };

  async function submitDriver(event) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await createFleetDriver({
        ...form,
        phone: form.phone || null,
        permis_numero: form.permis_numero || null,
        camion_defaut_id: form.camion_defaut_id ? Number(form.camion_defaut_id) : null,
        shift_start: form.shift_start || null,
        shift_end: form.shift_end || null,
      });
      await loadRoster();
      setForm(EMPTY_FORM);
      setShowForm(false);
    } catch (err) {
      setError(err.message || 'Unable to create driver');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f8f7f3] p-8">
      <div className="mb-8 flex flex-col gap-4 rounded-[2rem] border border-[#e8e5df] bg-white p-8 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.24em] text-[#7c3aed]">Driver operations</p>
          <h1 className="mt-3 text-4xl font-bold text-[#1a1a2e]">Driver roster</h1>
          <p className="mt-2 text-sm text-[#6b6b7b]">Persistent availability, licences, shifts, and default vehicle assignments.</p>
        </div>
        <button type="button" onClick={() => setShowForm(true)} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-[#7c3aed] px-5 py-3 font-semibold text-white">
          <Plus size={18} /> Add driver
        </button>
      </div>

      {error && <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700">{error}</div>}

      <div className="mb-8 grid gap-6 xl:grid-cols-3">
        {[
          ['Drivers', summary.total, Users],
          ['Active', summary.active, CheckCircle],
          ['Night shift', summary.nightShift, Clock3],
        ].map(([label, value, Icon]) => (
          <motion.div key={label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="rounded-[1.75rem] border border-[#e8e5eb] bg-white p-6 shadow-sm">
            <span className="inline-flex rounded-2xl bg-[#f3f0ff] p-3 text-[#7c3aed]"><Icon size={20} /></span>
            <p className="mt-4 text-xs uppercase tracking-[0.3em] text-[#6b7280]">{label}</p>
            <p className="mt-2 text-4xl font-semibold text-[#111827]">{value}</p>
          </motion.div>
        ))}
      </div>

      <div className="overflow-hidden rounded-[2rem] border border-[#e8e5df] bg-white shadow-sm">
        <div className="grid grid-cols-[1.7fr_0.8fr_1fr_1fr_0.8fr] gap-4 bg-[#f8f7f3] px-6 py-4 text-xs font-semibold uppercase tracking-[0.14em] text-[#6b7280]">
          <span>Driver</span><span>Licence</span><span>Shift</span><span>Truck</span><span>Status</span>
        </div>
        <div className="divide-y divide-[#e8e5df]">
          {drivers.map((driver) => (
            <div key={driver.id} className="grid grid-cols-[1.7fr_0.8fr_1fr_1fr_0.8fr] gap-4 px-6 py-4 text-sm text-[#1a1a2e]">
              <div><p className="font-semibold">{driver.full_name}</p><p className="text-xs text-[#6b7280]">{driver.phone || 'No phone'}</p></div>
              <div><p className="font-semibold">{driver.permis_type}</p><p className="text-xs text-[#6b7280]">{driver.permis_numero || '—'}</p></div>
              <span>{driver.shift_start?.slice(0, 5) || '—'}–{driver.shift_end?.slice(0, 5) || '—'}</span>
              <span>{truckLabels[driver.camion_defaut_id] || 'Unassigned'}</span>
              <span className={driver.status === 'ACTIF' ? 'text-emerald-700' : 'text-amber-700'}>{driver.status}</span>
            </div>
          ))}
          {drivers.length === 0 && <p className="p-8 text-center text-sm text-[#6b7280]">No drivers found.</p>}
        </div>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form onSubmit={submitDriver} className="w-full max-w-2xl rounded-[2rem] bg-white p-7 shadow-2xl">
            <div className="mb-6 flex items-center justify-between"><h2 className="text-2xl font-bold text-[#1a1a2e]">Add driver</h2><button type="button" onClick={() => setShowForm(false)}><X /></button></div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name"><input required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
              <Field label="Phone"><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
              <Field label="Licence type"><select value={form.permis_type} onChange={(e) => setForm({ ...form, permis_type: e.target.value })}>{['B', 'C', 'CE', 'D'].map((v) => <option key={v}>{v}</option>)}</select></Field>
              <Field label="Licence number"><input value={form.permis_numero} onChange={(e) => setForm({ ...form, permis_numero: e.target.value })} /></Field>
              <Field label="Shift start"><input type="time" value={form.shift_start} onChange={(e) => setForm({ ...form, shift_start: e.target.value })} /></Field>
              <Field label="Shift end"><input type="time" value={form.shift_end} onChange={(e) => setForm({ ...form, shift_end: e.target.value })} /></Field>
              <Field label="Default truck"><select value={form.camion_defaut_id} onChange={(e) => setForm({ ...form, camion_defaut_id: e.target.value })}><option value="">Unassigned</option>{trucks.map((truck) => <option key={truck.id} value={truck.id}>{truck.plate_number}</option>)}</select></Field>
              <Field label="Status"><select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>{['ACTIF', 'CONGE', 'ARRET_MALADIE', 'INACTIF'].map((v) => <option key={v}>{v}</option>)}</select></Field>
            </div>
            <div className="mt-7 flex justify-end gap-3"><button type="button" onClick={() => setShowForm(false)} className="rounded-xl px-5 py-2 text-[#6b7280]">Cancel</button><button disabled={saving} className="rounded-xl bg-[#7c3aed] px-5 py-2 font-semibold text-white disabled:opacity-50">{saving ? 'Saving…' : 'Create driver'}</button></div>
          </form>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return <label className="text-sm font-medium text-[#374151]"><span className="mb-2 block">{label}</span><span className="block [&>*]:w-full [&>*]:rounded-xl [&>*]:border [&>*]:border-[#ddd8cf] [&>*]:px-3 [&>*]:py-2.5 [&>*]:outline-none">{children}</span></label>;
}
