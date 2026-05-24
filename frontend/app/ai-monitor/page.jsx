"use client";

import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bell,
  Clock3,
  Cpu,
  Layers,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { getAgentStatus, generateOptimizationPlanning } from '../services/api';

const agentCards = [
  {
    key: 'collector',
    name: 'Agent 1 Collector',
    description: 'Watchdog and ingestion worker',
    icon: Cpu,
  },
  {
    key: 'optimizer',
    name: 'Agent 2 Optimizer',
    description: 'Route optimizer and planner',
    icon: Sparkles,
  },
  {
    key: 'notifier',
    name: 'Agent 3 Notifier',
    description: 'Alerts and notification engine',
    icon: Bell,
  },
  {
    key: 'monitor',
    name: 'Agent 4 Monitor',
    description: 'Live tracking and delay watcher',
    icon: Activity,
  },
];

const timelineSteps = [
  { key: 'trigger_15h00', label: '15:00 Watchdog' },
  { key: 'data_ready', label: '15:00 Validation' },
  { key: 'optimization_complete', label: '15:05 OR-Tools' },
  { key: 'alerts_pending', label: 'Post-15h Alert?' },
];

function getStepStyle(stepStatus) {
  if (stepStatus === 'done') return 'bg-emerald-500/15 border-emerald-400 text-emerald-200';
  if (stepStatus === 'current') return 'bg-amber-500/10 border-amber-400 text-amber-200';
  return 'bg-slate-800 border-slate-700 text-slate-400';
}

export default function AiMonitorPage() {
  const [statusData, setStatusData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [alertDismissed, setAlertDismissed] = useState(false);
  const [replanStatus, setReplanStatus] = useState('');

  useEffect(() => {
    let mounted = true;
    const fetchStatus = async () => {
      try {
        const data = await getAgentStatus();
        if (!mounted) return;
        setStatusData(data);
        setLoading(false);
        setError(null);
      } catch (err) {
        if (!mounted) return;
        setError('Unable to load AI monitor data.');
        setLoading(false);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const alertEvent = useMemo(() => {
    if (!statusData || alertDismissed) return null;
    return statusData.recent_events?.find((event) => event.event_name === 'post_deadline_modification');
  }, [statusData, alertDismissed]);

  const handleReplan = async () => {
    setReplanStatus('pending');
    try {
      await generateOptimizationPlanning();
      setReplanStatus('success');
    } catch (err) {
      setReplanStatus('error');
    }
  };

  const pipelineState = (stepIndex) => {
    if (!statusData) return 'waiting';
    const completed = statusData.pipeline_status[ timelineSteps[stepIndex].key ];
    if (completed) return 'done';

    if (stepIndex === 0) return 'current';
    const previousStepDone = statusData.pipeline_status[ timelineSteps[stepIndex - 1].key ];
    return previousStepDone ? 'current' : 'waiting';
  };

  return (
    <div className="min-h-screen bg-[#100b1f] text-white px-6 py-6">
      <div className="mx-auto flex max-w-[1480px] flex-col gap-6">
        <div className="rounded-[32px] border border-white/10 bg-[#1b1335]/90 p-8 shadow-2xl shadow-violet-950/40">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.32em] text-violet-300/70">AI Brain</p>
              <h1 className="mt-3 text-4xl font-semibold text-white">Agent Monitor</h1>
              <p className="mt-2 max-w-2xl text-sm text-slate-300">
                Real-time AI agent health, Redis event flow, and decision timeline for the operational pipeline.
              </p>
            </div>
            <div className="rounded-3xl bg-white/5 px-5 py-4 text-sm text-slate-200 ring-1 ring-white/10">
              Live refresh every 3 seconds
            </div>
          </div>
        </div>

        <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <div className="grid gap-6">
            <div className="rounded-[32px] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-slate-950/20">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm uppercase tracking-[0.32em] text-violet-200/70">Agent Status Panel</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">4 AI agents in action</h2>
                </div>
                <div className="inline-flex items-center gap-2 rounded-3xl bg-violet-500/15 px-4 py-2 text-sm text-violet-100">
                  <Layers size={18} /> Live status
                </div>
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                {agentCards.map(({ key, name, description, icon: Icon }) => {
                  const agent = statusData?.agents?.[key] || {};
                  return (
                    <div key={key} className="rounded-3xl border border-white/10 bg-slate-950/80 p-5 shadow-sm shadow-black/20">
                      <div className="flex items-center justify-between gap-4">
                        <div>
                          <p className="text-sm uppercase tracking-[0.3em] text-slate-400">{name}</p>
                          <p className="mt-2 text-base font-semibold text-white">{description}</p>
                        </div>
                        <div className="flex h-12 w-12 items-center justify-center rounded-3xl bg-violet-500/15 text-violet-200">
                          <Icon size={22} />
                        </div>
                      </div>
                      <div className="mt-5 space-y-3 text-sm text-slate-300">
                        <div className="flex items-center justify-between gap-4 rounded-3xl bg-white/5 px-4 py-3">
                          <span>Status</span>
                          <span className="font-semibold text-white">{agent.status || 'loading'}</span>
                        </div>
                        {key === 'optimizer' ? (
                          <div className="flex items-center justify-between gap-4 rounded-3xl bg-white/5 px-4 py-3">
                            <span>Last optimization</span>
                            <span className="font-semibold text-white">{agent.last_optimization_time || '—'}</span>
                          </div>
                        ) : null}
                        {key === 'notifier' ? (
                          <div className="flex items-center justify-between gap-4 rounded-3xl bg-white/5 px-4 py-3">
                            <span>Pending alerts</span>
                            <span className="font-semibold text-white">{agent.pending_alerts ?? 0}</span>
                          </div>
                        ) : null}
                        {key === 'monitor' ? (
                          <div className="flex items-center justify-between gap-4 rounded-3xl bg-white/5 px-4 py-3">
                            <span>Last poll</span>
                            <span className="font-semibold text-white">{agent.last_poll || '—'}</span>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-[32px] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-slate-950/20">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm uppercase tracking-[0.32em] text-violet-200/70">Decision Timeline</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">Pipeline progress</h2>
                </div>
                <div className="text-sm text-slate-400">15h00 orchestration</div>
              </div>
              <div className="mt-6 flex flex-wrap items-center gap-4">
                {timelineSteps.map((step, index) => {
                  const state = pipelineState(index);
                  return (
                    <div key={step.key} className={`flex min-w-[180px] items-center gap-3 rounded-3xl border px-4 py-4 ${getStepStyle(state)} border-white/10`}>
                      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/5 text-base font-semibold text-white">
                        {index + 1}
                      </div>
                      <div>
                        <p className="text-sm uppercase tracking-[0.28em] text-slate-400">{step.label}</p>
                        <p className="mt-1 text-sm font-medium text-white">
                          {state === 'done' ? 'Done' : state === 'current' ? 'In progress' : 'Waiting'}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="grid gap-6">
            <div className="rounded-[32px] border border-white/10 bg-[#121025]/95 p-6 shadow-2xl shadow-slate-950/40">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm uppercase tracking-[0.32em] text-violet-200/70">Live Event Stream</p>
                  <h2 className="mt-2 text-2xl font-semibold text-white">Redis-inspired activity feed</h2>
                </div>
                <div className="inline-flex items-center gap-2 rounded-full bg-slate-800/90 px-4 py-2 text-sm text-slate-300 ring-1 ring-white/10">
                  <Clock3 size={16} /> {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>

              <div className="mt-6 space-y-3 overflow-hidden rounded-3xl border border-white/10 bg-slate-950/80 p-4">
                {loading ? (
                  <div className="rounded-3xl bg-slate-900/80 px-5 py-7 text-center text-sm text-slate-400">Loading stream...</div>
                ) : error ? (
                  <div className="rounded-3xl bg-rose-500/10 px-5 py-7 text-sm text-rose-200">{error}</div>
                ) : (
                  statusData?.recent_events?.map((event) => (
                    <div key={`${event.timestamp}-${event.event_name}`} className="grid grid-cols-[110px_minmax(0,1fr)_120px] gap-4 rounded-3xl bg-white/5 px-4 py-4 text-sm text-slate-200 transition-all hover:bg-white/10">
                      <div className="font-mono text-slate-400">{event.timestamp}</div>
                      <div>
                        <p className="font-semibold text-white">{event.event_name}</p>
                        <p className="text-slate-400">{event.payload_summary}</p>
                      </div>
                      <div className="rounded-2xl bg-slate-900/80 px-3 py-2 text-right text-xs uppercase tracking-[0.22em] text-slate-400">
                        {event.source_agent}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {alertEvent ? (
              <div className="rounded-[32px] border border-amber-400/20 bg-amber-500/10 p-6 shadow-2xl shadow-amber-950/20">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm uppercase tracking-[0.32em] text-amber-200/80">Alert Action Panel</p>
                    <h2 className="mt-2 text-2xl font-semibold text-white">Modification détectée après 15h00</h2>
                    <p className="mt-3 max-w-xl text-sm text-amber-100/80">
                      {alertEvent.payload_summary}
                    </p>
                  </div>
                  <div className="rounded-full bg-amber-500/20 px-4 py-2 text-xs uppercase tracking-[0.28em] text-amber-100">
                    {alertEvent.source_agent}
                  </div>
                </div>

                <div className="mt-6 grid gap-4">
                  <div className="grid gap-2 rounded-3xl bg-slate-950/70 p-4 text-sm text-slate-200">
                    <div className="flex items-center justify-between gap-4 text-slate-400">
                      <span>Client</span>
                      <span>ACME Industries</span>
                    </div>
                    <div className="flex items-center justify-between gap-4 text-slate-400">
                      <span>Detail</span>
                      <span>Post-deadline route modification</span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-3 sm:flex-row">
                    <button
                      type="button"
                      onClick={handleReplan}
                      className="inline-flex items-center justify-center rounded-3xl bg-emerald-500 px-5 py-3 text-sm font-semibold text-white transition hover:bg-emerald-400"
                    >
                      ✅ Replanifier
                    </button>
                    <button
                      type="button"
                      onClick={() => setAlertDismissed(true)}
                      className="inline-flex items-center justify-center rounded-3xl border border-white/10 bg-slate-900/90 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:border-amber-300 hover:text-amber-200"
                    >
                      ❌ Ignorer
                    </button>
                  </div>
                  {replanStatus === 'pending' ? (
                    <div className="text-sm text-slate-200">Replanning request in progress...</div>
                  ) : replanStatus === 'success' ? (
                    <div className="text-sm text-emerald-300">Replanification envoyée.</div>
                  ) : replanStatus === 'error' ? (
                    <div className="text-sm text-rose-300">Impossible de replanifier pour le moment.</div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
