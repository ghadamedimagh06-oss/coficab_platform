"use client";

import { useState } from 'react';
import { processDataTask, syncDailyPlanning, triggerIngestion } from '../services/api';
import ChatPanel from '../../components/chat/ChatPanel';
import StatCard from '../../components/cards/StatCard';

export default function AdminPage() {
  const [filePath, setFilePath] = useState('shared_folder/sample_transport_data.xlsx');
  const [actionResult, setActionResult] = useState('Ready to ingest data.');
  const [chatMessages, setChatMessages] = useState([`Admin panel is online. Track ingestion and sync events here.`]);

  const doIngestion = async () => {
    try {
      const result = await triggerIngestion(filePath);
      setActionResult(`Ingestion started: ${result.rows_inserted ?? 'pending'} rows`);
      setChatMessages((prev) => [`Ingestion triggered for ${filePath}.`, ...prev]);
    } catch (error) {
      setActionResult('Ingestion failed.');
      setChatMessages((prev) => ['Ingestion API failed. Check file path or backend.', ...prev]);
    }
  };

  const doSync = async () => {
    try {
      const result = await syncDailyPlanning();
      setActionResult('Daily planning sync requested.');
      setChatMessages((prev) => [`Daily planning sync triggered.`, ...prev]);
    } catch (error) {
      setActionResult('Sync failed.');
      setChatMessages((prev) => ['Sync endpoint is unavailable. Verify backend.', ...prev]);
    }
  };

  const doProcess = async () => {
    try {
      const result = await processDataTask();
      setActionResult('Data processing workflow started.');
      setChatMessages((prev) => ['Automated processing task requested.', ...prev]);
    } catch (error) {
      setActionResult('Processing task failed.');
      setChatMessages((prev) => ['Processing task failed. Review backend logs.', ...prev]);
    }
  };

  return (
    <div className="grid gap-8 xl:grid-cols-[1.4fr_0.9fr]">
      <section className="space-y-6">
        <div className="grid gap-6 sm:grid-cols-3">
          <StatCard title="Excel ingestion" value="Shared folder" hint="Watchdog file ingestion source" icon="📄" />
          <StatCard title="Sync tasks" value="Automated" hint="AI and planning orchestration" icon="🤖" />
          <StatCard title="Audit log" value="Enabled" hint="Change reason capture" icon="🧾" />
        </div>

        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <h2 className="text-2xl font-semibold">Ingestion & control panel</h2>
          <p className="mt-3 text-sm text-slate-400">Use this panel to control file ingestion, schedule syncs, and monitor automated tasks.</p>

          <div className="mt-8 space-y-6">
            <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-6">
              <label className="text-sm text-slate-400">Excel file path</label>
              <input
                value={filePath}
                onChange={(event) => setFilePath(event.target.value)}
                className="mt-3 w-full rounded-3xl border border-slate-800 bg-slate-900/90 p-4 text-slate-100 outline-none focus:border-brand"
                placeholder="shared_folder/my_plan.xlsx"
              />
              <button onClick={doIngestion} className="mt-4 rounded-3xl bg-brand px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition">
                Trigger ingestion
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <button onClick={doSync} className="rounded-3xl bg-slate-800 px-5 py-4 text-left text-sm font-semibold text-slate-100 hover:bg-slate-700 transition">
                Sync daily planning
                <p className="mt-2 text-slate-400 text-xs">Request the scheduler to refresh planning data.</p>
              </button>
              <button onClick={doProcess} className="rounded-3xl bg-slate-800 px-5 py-4 text-left text-sm font-semibold text-slate-100 hover:bg-slate-700 transition">
                Start automation task
                <p className="mt-2 text-slate-400 text-xs">Trigger backend processing pipeline.</p>
              </button>
            </div>

            <div className="rounded-3xl border border-slate-800 bg-slate-950/80 p-5 text-sm text-slate-300">
              <p className="font-semibold">Latest action</p>
              <p className="mt-2">{actionResult}</p>
            </div>
          </div>
        </div>
      </section>

      <aside className="space-y-6">
        <div className="rounded-[2rem] border border-slate-800 bg-[var(--surface)] p-6 shadow-xl shadow-black/20">
          <h2 className="text-xl font-semibold">Admin notes</h2>
          <p className="mt-3 text-sm text-slate-400">In a demo-ready environment, this panel demonstrates secure ingestion, synchronization, and operational control for logistics operators.</p>
        </div>

        <ChatPanel messages={chatMessages} />
      </aside>
    </div>
  );
}
