"use client";

import Sidebar from './Sidebar';

export default function AppShell({ children }) {
  return (
    <div className="flex min-h-screen bg-[#faf8f5] text-[#1a1a2e]">
      <Sidebar />
      <main className="min-w-0 flex-1 pb-12 pl-72">
        <div className="sticky top-0 z-40 bg-[#faf8f5]/95 backdrop-blur-xl border-b border-[#e8e5df] px-6 py-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.32em] text-[#6b6b7b]">COFICAB Control Tower</p>
              <h1 className="text-2xl font-semibold">Live operations</h1>
            </div>
            <div className="flex flex-wrap gap-3">
              <span className="rounded-2xl border border-[#e8e5df] bg-white px-4 py-2 text-sm text-[#6b6b7b]">Live state</span>
              <span className="rounded-2xl border border-[#e8e5df] bg-white px-4 py-2 text-sm text-[#6b6b7b]">Audit ready</span>
            </div>
          </div>
        </div>
        <div className="px-6 pt-6">{children}</div>
      </main>
    </div>
  );
}
