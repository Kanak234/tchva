'use client';

import { useEffect } from 'react';

export default function RegisterSW() {
  useEffect(() => {
    if (
      typeof window !== 'undefined' &&
      'serviceWorker' in navigator &&
      process.env.NODE_ENV === 'production'
    ) {
      window.addEventListener('load', () => {
        navigator.serviceWorker
          .register('/sw.js')
          .then((reg) => console.log('Service Worker registered successfully:', reg.scope))
          .catch((err) => console.error('Service Worker registration failed:', err));
      });
    }
  }, []);

  return null;
}
