"use client";
/**
 * Login — Google Sign-In.
 */
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { t, type Lang } from "@/lib/i18n";
import {
  signInWithGoogle,
  canSignIn,
  watchAuth,
  DEMO_MODE,
} from "@/lib/auth";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("hi");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("fk_lang") as Lang | null;
    if (stored) setLang(stored);
  }, []);

  // If Firebase restores a session, skip straight past this screen.
  useEffect(() => {
    return watchAuth(async (user) => {
      if (!user) return;
      await routeAfterSignIn();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * After sign-in, ask the API which farms this account owns.
   * localStorage is a cache, not a source of truth.
   */
  async function routeAfterSignIn() {
    try {
      const mine = await api.myFarms();
      if (mine.count > 0) {
        localStorage.setItem("fk_farm_id", mine.farms[0].farm_id);
        router.replace(`/farm/${mine.farms[0].farm_id}`);
        return;
      }
    } catch {
      /* fall through to onboarding */
    }
    router.replace("/onboarding");
  }

  async function handleGoogleSignIn() {
    setBusy(true);
    setError("");
    const err = await signInWithGoogle();
    setBusy(false);
    if (err) {
      setError(err);
      return;
    }
    await routeAfterSignIn();
  }

  function useDemoAccount() {
    localStorage.setItem("fk_demo", "true");
    localStorage.setItem("fk_farm_id", "f_demo_01");
    router.push("/farm/f_demo_01");
  }

  const configured = canSignIn();

  return (
    <main
      style={{
        minHeight: "100dvh",
        background: "var(--surface-alt)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div className="top-header" style={{ textAlign: "center", padding: "32px 24px 24px" }}>
        <div style={{ fontSize: "2.5rem", marginBottom: "8px" }}>🌾</div>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 800, color: "white", margin: 0 }}>
          Fasal Kavach
        </h1>
        <p style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.9rem", marginTop: "4px" }}>
          {t("login.subtitle", lang)}
        </p>
      </div>

      <div style={{ flex: 1, padding: "32px 24px", maxWidth: 420, margin: "0 auto", width: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <button
          onClick={handleGoogleSignIn}
          disabled={!configured || busy}
          style={{
            width: "100%",
            padding: "16px",
            fontSize: "1.1rem",
            fontWeight: 600,
            color: "#3c4043",
            background: "#ffffff",
            border: "1px solid #dadce0",
            borderRadius: 12,
            cursor: (!configured || busy) ? "default" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "12px",
            boxShadow: "0 1px 3px 0 rgba(60,64,67,0.3), 0 4px 8px 3px rgba(60,64,67,0.15)",
            opacity: (!configured || busy) ? 0.7 : 1,
            transition: "background-color .218s, border-color .218s, box-shadow .218s",
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
          </svg>
          {busy ? t("login.sending", lang) : t("login.google", lang)}
        </button>

        {error && (
          <div
            role="alert"
            style={{
              marginTop: 20,
              padding: "12px 14px",
              borderRadius: 10,
              background: "#FDECEA",
              color: "#8A1C11",
              fontSize: "0.95rem",
              border: "1px solid #F5C2BC",
              textAlign: "center",
            }}
          >
            {error}
          </div>
        )}

        {!configured && (
          <div
            style={{
              marginTop: 20,
              padding: "12px 14px",
              borderRadius: 10,
              background: "#FFF6E5",
              color: "#7A4A00",
              fontSize: "0.9rem",
              border: "1px solid #F0DCB4",
              textAlign: "center",
            }}
          >
            {t("login.notConfigured", lang)}
          </div>
        )}
      </div>

      {DEMO_MODE && (
        <div style={{ padding: "16px 24px 40px", textAlign: "center" }}>
          <button
            onClick={useDemoAccount}
            style={{
              color: "var(--accent)",
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "0.95rem",
              fontWeight: 600,
            }}
          >
            {t("login.demo", lang)}
          </button>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.78rem", marginTop: 6 }}>
            {t("login.demoNote", lang)}
          </p>
        </div>
      )}
    </main>
  );
}
