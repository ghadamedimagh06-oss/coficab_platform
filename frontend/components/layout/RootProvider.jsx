"use client";

import { useEffect, useState } from 'react';
import AppShell from './AppShell';

export default function RootProvider({ children }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div>{children}</div>;
  }

  return <AppShell>{children}</AppShell>;
}
