"use client";

import { useEffect, useMemo, useState } from 'react';
import { getTransports, proposeOptimization, updatePlanning, validatePlanning } from '../services/api';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';
import JustificationModal from '../../components/JustificationModal';

function moveItem(items, from, to) {
  const next = [...items];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

export default function PlanningPage() {
  const [mode, setMode] = useState('ai');
  const [plan, setPlan] = useState([]);
  const [validated, setValidated] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [dragIndex, setDragIndex] = useState(null);
  const [pendingPlan, setPendingPlan] = useState(null);
  const [pendingChange, setPendingChange] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [planningId] = useState(1);
  const [currentUserId] = useState(1);

  useEffect(() => {
    async function fetchPlan() {
      try {
        const transports = await getTransports();
        const items = (Array.isArray(transports) ? transports : []).slice(0, 6).map((item, index) => ({
          id: item.id || String(index + 1),
          truck: item.vehicle || `Truck ${index + 1}`,
          client: item.end_location || 'Client location',
          eta: `${3 + index}h`, 
          risk: index % 3 === 0 ? 'Low' : index % 3 === 1 ? 'Medium' : 'High',
          status: index % 3 === 0 ? 'On time' : index % 3 === 1 ? 'Slight delay' : 'Critical delay',
        }));
        setPlan(items);
        setChatMessages(['Planning module initialized with route candidates.']);
      } catch (error) {
        setChatMessages(['Unable to load transport plan. Check backend connectivity.']);
      }
    }
    fetchPlan();
  }, []);

  const routeSummary = useMemo(() => {
    return {
      trucks: plan.length,
      risk: plan.filter((item) => item.status.toLowerCase().includes('critical')).length,
      eta: plan.length ? `${plan.length * 2 + 1}h` : '0h',
    };
  }, [plan]);

  const applyPlan = async () => {
    if (mode !== 'ai') return;
    try {
      const response = await proposeOptimization({ transports: plan });
      const optimized = response?.routes || plan;
      setPlan(optimized.map((item, index) => ({
        ...item,
        id: item.id || String(index + 1),
        truck: item.truck || item.vehicle || `Truck ${index + 1}`,
      })));
      setChatMessages((prev) => ['AI plan proposal loaded. Review before validation.', ...prev]);
    } catch (error) {
      setChatMessages((prev) => ['AI optimization failed. Using the current manual plan instead.', ...prev]);
    }
  };

  const handleDrop = async (targetIndex) => {
    if (dragIndex === null) return;
    const nextPlan = moveItem(plan, dragIndex, targetIndex);

    if (validated) {
      setPendingPlan(nextPlan);
      setPendingChange({
        planning_id: planningId,
        field_changed: 'route_order',
        old_value: JSON.stringify(plan),
        new_value: JSON.stringify(nextPlan),
      });
      setShowModal(true);
      return;
    }

    setPlan(nextPlan);
    setChatMessages((prev) => ['Route order updated successfully.', ...prev]);
  };

  const confirmChange = async ({ reason_category, reason_text }) => {
    if (!pendingPlan || !pendingChange) return;

    try {
      await updatePlanning({
        ...pendingChange,
        reason_category,
        reason_text,
        user_id: currentUserId,
      });
      setPlan(pendingPlan);
      setValidated(true);
      setChatMessages((prev) => [`Justified planning change applied (${reason_category}).`, ...prev]);
    } catch (error) {
      setChatMessages((prev) => ['Unable to apply justified change. Please try again.', ...prev]);
    } finally {
      setPendingPlan(null);
      setPendingChange(null);
      setShowModal(false);
    }
  };

  const toggleValidation = async () => {
    if (validated) {
      setValidated(false);
      setChatMessages((prev) => ['Planning unlocked for free editing.', ...prev]);
      return;
    }

    try {
      await validatePlanning(planningId, currentUserId);
      setValidated(true);
      setChatMessages((prev) => ['Planning validated. Further changes will require a justification.', ...prev]);
    } catch (error) {
      setChatMessages((prev) => ['Unable to validate planning. Check backend connectivity.', ...prev]);
    }
  };

  return (
    <div className="grid gap-8 xl:grid-cols-[1.45fr_0.95fr]">
      <section className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-3">
          <StatCard title="Planned routes" value={routeSummary.trucks} hint="Routes in the current execution plan" icon="🗺️" />
          <StatCard title="Critical risk" value={routeSummary.risk} hint="Routes requiring attention" icon="⚠️" />
          <StatCard title="ETA impact" value={routeSummary.eta} hint="Estimated completion horizon" icon="⏳" />
        </div>

        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm text-slate-400">Planning workspace</p>
              <h2 className="text-2xl font-semibold">AI and manual route planning</h2>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <button onClick={() => setMode('ai')} className={`rounded-full px-5 py-3 text-sm transition ${mode === 'ai' ? 'bg-brand text-slate-900' : 'bg-slate-800 text-slate-300'}`}>
                AI Mode
              </button>
              <button onClick={() => setMode('manual')} className={`rounded-full px-5 py-3 text-sm transition ${mode === 'manual' ? 'bg-brand text-slate-900' : 'bg-slate-800 text-slate-300'}`}>
                Manual Mode
              </button>
              {mode === 'ai' && (
                <button onClick={applyPlan} className="rounded-full bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400">
                  Load AI Plan
                </button>
              )}
            </div>
          </div>

          <div className="overflow-hidden rounded-[1.5rem] border border-slate-800 bg-slate-950/70">
            <div className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr] gap-4 px-6 py-4 text-sm uppercase tracking-[0.18em] text-slate-500">
              <span>Truck</span>
              <span>Client</span>
              <span>ETA</span>
              <span>Risk</span>
              <span>Status</span>
            </div>
            <div className="divide-y divide-slate-900">
              {plan.map((item, index) => (
                <div
                  key={item.id}
                  draggable={mode === 'manual'}
                  onDragStart={() => setDragIndex(index)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => handleDrop(index)}
                  className={`grid grid-cols-[1fr_1fr_1fr_1fr_1fr] gap-4 px-6 py-5 transition ${mode === 'manual' ? 'cursor-grab hover:bg-slate-900/80' : ''}`}
                >
                  <span className="font-semibold">{item.truck}</span>
                  <span className="text-slate-300">{item.client}</span>
                  <span>{item.eta}</span>
                  <span>{item.risk}</span>
                  <span className={item.status.toLowerCase().includes('critical') ? 'text-rose-400' : item.status.toLowerCase().includes('delay') ? 'text-orange-300' : 'text-emerald-300'}>{item.status}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <button onClick={toggleValidation} className="rounded-3xl bg-brand px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400">
              {validated ? 'Unlock planning' : 'Validate planning'}
            </button>
            <p className="text-sm text-slate-400">{validated ? 'Validated plan: changes will log a justification.' : 'Free editing is enabled.'}</p>
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <h2 className="text-xl font-semibold">Planning actions</h2>
          <p className="mt-3 text-sm text-slate-400">Drag and drop route rows when manual mode is active. Validated plans require a justification for every update, preserving audit history.</p>
        </div>

        <ChatPanel messages={chatMessages} />
      </aside>

      {showModal && pendingChange ? (
        <JustificationModal
          change={{
            planning_id: pendingChange.planning_id,
            field: pendingChange.field_changed,
            oldValue: pendingChange.old_value,
            newValue: pendingChange.new_value,
          }}
          onConfirm={confirmChange}
          onCancel={() => {
            setShowModal(false);
            setPendingPlan(null);
            setPendingChange(null);
          }}
        />
      ) : null}
    </div>
  );
}
