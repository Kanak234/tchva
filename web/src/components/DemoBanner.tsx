'use client';
/**
 * Demo banner — visible only when api.ts has fallen back to mock data.
 *
 * This must be impossible to miss. Someone judging a demo needs to know
 * instantly that the numbers on screen are simulated, not live.
 */
import { useEffect, useState } from 'react';
import { subscribeToMockMode } from '@/lib/api';
import { t, type Lang } from '@/lib/i18n';

export default function DemoBanner() {
  const [isMock, setIsMock] = useState(false);
  const [lang, setLang] = useState<Lang>('hi');

  useEffect(() => {
    const storedLang = localStorage.getItem('fk_lang') as Lang | null;
    if (storedLang) setLang(storedLang);

    const checkLang = () => {
      const stored = localStorage.getItem('fk_lang') as Lang | null;
      if (stored && stored !== lang) setLang(stored);
    };
    const interval = setInterval(checkLang, 1000);
    const unsub = subscribeToMockMode(setIsMock);

    return () => {
      clearInterval(interval);
      unsub();
    };
  }, [lang]);

  if (!isMock) return null;

  return (
    <div
      id="demo-mode-warning-banner"
      role="status"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 9999,
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        padding: '8px 16px',
        background: 'var(--turmeric)',
        color: '#FFF8EC',
        fontFamily: 'var(--face-display)',
        fontSize: '0.66rem',
        fontWeight: 700,
        letterSpacing: '0.11em',
        textTransform: 'uppercase',
        textAlign: 'center',
        /* Hazard hatch — the same vernacular as a severe advisory stripe */
        backgroundImage:
          'repeating-linear-gradient(45deg, rgba(0,0,0,0.07) 0px, rgba(0,0,0,0.07) 6px, transparent 6px, transparent 16px)',
      }}
    >
      {t('demo.mockWarning', lang)}
    </div>
  );
}
