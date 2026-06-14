"use client";

import { useEffect, useState } from 'react';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar';
import CopilotLauncher from '../chat/CopilotLauncher';

export default function AppShell({ children }) {
  // Drawer is closed by default on mobile; on lg+ the sidebar is visible unless
  // the user collapses it. `isSidebarOpen` drives the mobile overlay, while
  // `isCollapsed` drives the desktop show/hide toggle.
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Restore the persisted desktop collapse state on mount.
  useEffect(() => {
    try {
      if (localStorage.getItem('sidebarCollapsed') === '1') setIsCollapsed(true);
    } catch {}
  }, []);

  // Persist the collapse state whenever it changes.
  useEffect(() => {
    try {
      localStorage.setItem('sidebarCollapsed', isCollapsed ? '1' : '0');
    } catch {}
  }, [isCollapsed]);

  // Ctrl/Cmd+B toggles the sidebar, mirroring the common editor shortcut.
  useEffect(() => {
    function onKey(e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B')) {
        e.preventDefault();
        setIsCollapsed((v) => !v);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      <Sidebar
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        isCollapsed={isCollapsed}
        onToggleCollapse={() => setIsCollapsed((v) => !v)}
      />

      <main
        className={`min-w-0 flex-1 pb-12 transition-[padding] duration-300 ease-in-out ${
          isCollapsed ? 'lg:pl-20' : 'lg:pl-72'
        }`}
      >
        {/* Mobile-only top bar: holds the hamburger. On lg+ each page owns
            its own header, so this bar is hidden to avoid a double header. */}
        <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-canvas/95 px-4 py-3 backdrop-blur-xl lg:hidden">
          <button
            type="button"
            onClick={() => setIsSidebarOpen(true)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-ink"
            aria-label="Open navigation menu"
          >
            <Menu size={20} />
          </button>
          <div>
            <p className="text-[11px] uppercase tracking-[0.28em] text-muted">COFICAB</p>
            <p className="text-sm font-semibold">OptiRoute</p>
          </div>
        </div>

        <div className="px-4 pt-6 lg:px-6">{children}</div>
      </main>

      {/* Global assistant — reachable from every page */}
      <CopilotLauncher />
    </div>
  );
}
