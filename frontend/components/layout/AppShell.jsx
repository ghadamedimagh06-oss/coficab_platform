"use client";

import Link from 'next/link';
import { useEffect, useState } from 'react';

const navItems = [
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'Map', href: '/map' },
  { label: 'Planning', href: '/planning' },
  { label: 'Analytics', href: '/analytics' },
  { label: 'Admin', href: '/admin' },
];

export default function AppShell({ children }) {
  const [theme, setTheme] = useState('dark');

  useEffect(() => {
    const saved = window.localStorage.getItem('coficab-theme');
    if (saved === 'light') {
      setTheme('light');
    }
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('light-theme');
    } else {
      root.classList.remove('light-theme');
    }
    window.localStorage.setItem('coficab-theme', theme);
  }, [theme]);

  return (
    <div className="min-h-screen flex bg-[var(--bg)] text-[var(--text)]">
      <aside className="hidden md:flex md:flex-col md:w-72 bg-slate-950/95 border-r border-slate-800 p-6 gap-8 sticky top-0 h-screen">
        <div>
          <div className="text-brand text-2xl font-semibold">COFICAB</div>
          <p className="text-slate-400 mt-2 text-sm">Logistics control tower</p>
        </div>
        <nav className="flex flex-col gap-2">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="rounded-3xl px-4 py-3 text-sm font-medium border border-slate-800 hover:bg-slate-800 transition-colors">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto">
          <button
            type="button"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="w-full rounded-3xl bg-slate-800 px-4 py-3 text-sm font-semibold text-slate-100 hover:bg-slate-700 transition"
          >
            Theme: {theme === 'dark' ? 'Dark' : 'Light'}
          </button>
        </div>
      </aside>

      <main className="flex-1 pb-12">
        <div className="flex items-center justify-between border-b border-slate-800/60 bg-[var(--surface)]/80 backdrop-blur-xl px-4 py-4 md:px-8 sticky top-0 z-20">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">COFICAB Control Room</p>
            <h1 className="text-2xl md:text-3xl font-semibold">Operational Logistics Dashboard</h1>
          </div>
          <div className="hidden sm:flex items-center gap-3 text-sm text-slate-300">
            <span className="rounded-full border border-slate-700 px-3 py-2 bg-slate-900/80">Polling live data</span>
            <span className="rounded-full border border-slate-700 px-3 py-2 bg-slate-900/80">Audit-ready workspace</span>
          </div>
        </div>
        <div className="px-4 md:px-8 pt-6">{children}</div>
      </main>
    </div>
  );
}
