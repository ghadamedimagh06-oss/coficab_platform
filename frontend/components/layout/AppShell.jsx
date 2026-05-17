"use client";

import Sidebar from './Sidebar';

export default function AppShell({ children }) {
  return (
    <div className="flex min-h-screen bg-[#faf8f5] text-[#1a1a2e]">
      <Sidebar />
      <main className="flex-1 pb-12 pl-72">
        <div className="sticky top-0 z-20 bg-[#faf8f5]/95 backdrop-blur-xl border-b border-[#e8e5df] px-6 py-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.32em] text-[#6b6b7b]">COFICAB Control Room</p>
              <h1 className="text-3xl font-semibold tracking-tight">Operational Logistics Dashboard</h1>
            </div>
            <div className="flex flex-wrap gap-3">
              <span className="rounded-2xl border border-[#e8e5df] bg-white px-4 py-2 text-sm text-[#6b6b7b]">Polling live data</span>
              <span className="rounded-2xl border border-[#e8e5df] bg-white px-4 py-2 text-sm text-[#6b6b7b]">Audit-ready workspace</span>
            </div>
          </div>
        </div>
        <div className="px-6 pt-6">{children}</div>
      </main>
    </div>
  );
}
