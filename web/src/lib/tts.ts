/**
 * TTS Layer — Section 22.3
 *
 * Browser text-to-speech for Indian languages.
 * Khortha has no TTS voice — the Hindi voice reads Devanagari
 * Khortha text intelligibly. Documented honestly.
 */

export type Lang = 'hi' | 'en' | 'kho' | 'bn';

const VOICE_LANG: Record<Lang, string> = {
  hi: 'hi-IN',
  en: 'en-IN',
  bn: 'bn-IN',
  kho: 'hi-IN', // Khortha: no dedicated voice; Hindi reads Devanagari acceptably
};

let currentUtterance: SpeechSynthesisUtterance | null = null;

export function speak(
  text: string,
  lang: Lang
): { supported: boolean; stop: () => void } {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    return { supported: false, stop: () => {} };
  }

  // Cancel any ongoing speech
  window.speechSynthesis.cancel();

  const u = new SpeechSynthesisUtterance(text);
  u.lang = VOICE_LANG[lang];
  u.rate = 0.9; // Slower reads better for warnings
  u.pitch = 1.0;
  u.volume = 1.0;

  currentUtterance = u;
  window.speechSynthesis.speak(u);

  return {
    supported: true,
    stop: () => {
      window.speechSynthesis.cancel();
      currentUtterance = null;
    },
  };
}

export function stopSpeaking(): void {
  if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
  if (currentUtterance) {
    currentUtterance = null;
  }
}

export function isSpeaking(): boolean {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
    return false;
  }
  return window.speechSynthesis.speaking;
}

export function isTTSSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}
