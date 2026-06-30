"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import AppShell from './AppShell';

// Standalone routes that render full-bleed, without the app chrome (sidebar /
// copilot launcher). The login screen owns the whole viewport.
const BARE_ROUTES = ['/login'];

// Session flag set by the login screen (app/login/page.jsx). Its presence is
// what gates access to the rest of the app.
const AUTH_KEY = 'optiroute_auth';

function isAuthenticated() {
  try {
    return !!window.localStorage.getItem(AUTH_KEY);
  } catch {
    return false;
  }
}

export default function RootProvider({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const bare = BARE_ROUTES.some((route) => pathname?.startsWith(route));

  // Guard: once mounted, bounce unauthenticated visitors to the login screen.
  useEffect(() => {
    if (mounted && !bare && !isAuthenticated()) {
      router.replace('/login');
    }
  }, [mounted, bare, pathname, router]);

  // Auth and other standalone pages skip the shell entirely.
  if (bare) {
    return <>{children}</>;
  }

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

  // Mounted but not signed in: keep protected content hidden, but show a real
  // fallback in case the client-side redirect is delayed or blocked.
  if (!isAuthenticated()) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-6 text-ink">
        <div className="w-full max-w-md rounded-[2rem] border border-border bg-white p-8 text-center shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-brand-600">Authentication</p>
          <h1 className="mt-3 text-2xl font-bold">Redirecting to sign in</h1>
          <p className="mt-2 text-sm leading-6 text-muted">
            Your session is not active. Use the sign-in screen to enter the platform.
          </p>
          <Link
            href="/login"
            className="mt-6 inline-flex items-center justify-center rounded-2xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
          >
            Open sign in
          </Link>
        </div>
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
