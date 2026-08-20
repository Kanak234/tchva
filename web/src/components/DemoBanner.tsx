'use client';

import React, { useEffect, useState } from 'react';
import { subscribeToMockMode } from '@/lib/api';
import { t, type Lang } from '@/lib/i18n';

export default function DemoBanner() {
  const [isMock, setIsMock] = useState(false);
  const [lang, setLang] = useState<Lang>('hi');

  useEffect(() => {
    // Read initial language
    const storedLang = localStorage.getItem('fk_lang') as Lang | null;
    if (storedLang) setLang(storedLang);

    // Listen for language changes locally
    const checkLang = () => {
      const stored = localStorage.getItem('fk_lang') as Lang | null;
      if (stored && stored !== lang) {
        setLang(stored);
      }
    };
    const interval = setInterval(checkLang, 1000);

    // Watch for mock mode state changes
    const unsub = subscribeToMockMode((active) => {
      setIsMock(active);
    });

    return () => {
      clearInterval(interval);
      unsub();
    };
  }, [lang]);

  if (!isMock) return null;

  return (
    <div 
      id="demo-mode-warning-banner"
      style={{
        backgroundColor: '#FEF3C7',
        borderBottom: '2px solid #B45309', // bold amber-700 border
        color: '#78350F',
        padding: '10px 16px',
        fontSize: '0.85rem',
        fontWeight: 700,
        textAlign: 'center',
        position: 'sticky',
        top: 0,
        zIndex: 9999,
        width: '100%',
        boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
      }}
    >
      {t('demo.mockWarning', lang)}
    </div>
  );
}
