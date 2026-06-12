"use client";

import { useEffect, useState } from 'react';
import AppShell from './AppShell';

export default function RootProvider({ children }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Before hydration, render a skeleton shell with the same outer geometry
  // as AppShell (sidebar gutter reserved on lg+) so there is no layout shift
  // when the interactive shell takes over.
  if (!mounted) {
    return (
      <div className="flex min-h-screen bg-canvas text-ink">
        <div
          className="hidden lg:block fixed left-0 top-0 h-screen w-72 bg-gradient-to-b from-brand-600 via-brand-700 to-brand-800"
          aria-hidden="true"
        />
        <main className="min-w-0 flex-1 pb-12 lg:pl-72">
          <div className="px-4 pt-6 lg:px-6">{children}</div>
        </main>
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
