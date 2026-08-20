'use client';

import React, { useEffect, useState } from 'react';
import { subscribeToBackendStatus } from '@/lib/api';

export default function DemoBanner() {
  const [disconnected, setDisconnected] = useState(false);

  useEffect(() => {
    return subscribeToBackendStatus((status) => {
      setDisconnected(status);
    });
  }, []);

  if (!disconnected) return null;

  return (
    <div className="bg-amber-100 border-b border-amber-300 text-amber-900 px-4 py-2.5 text-xs md:text-sm font-semibold flex items-center justify-center gap-2 sticky top-0 z-50 shadow-sm animate-pulse">
      <span>⚠️</span>
      <span>Demo Mode — Backend not connected. Advisories are simulated, not generated from live weather.</span>
    </div>
  );
}
