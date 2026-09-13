"use client";
/**
 * Login — Google Sign-In, with a demo farm as the escape hatch.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { t, type Lang } from "@/lib/i18n";
import { signInWithGoogle, canSignIn, watchAuth, getToken, DEMO_MODE } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { IconShield, IconGoogle, IconArrowLeft } from "@/components/Icons";

export default function LoginPage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("hi");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigatingRef = useRef(false);

  useEffect(() => {
    const stored = localStorage.getItem("fk_lang") as Lang | null;
    if (stored) setLang(stored);
  }, []);

  /**
   * After sign-in, verify that Firebase still has a usable ID token before
   * asking the API which farms this account owns. A backend/API failure is
   * an authentication/network error, not evidence that the user has no farm.
   */
  const routeAfterSignIn = useCallback(async () => {
    if (navigatingRef.current) return;
    navigatingRef.current = true;
    setBusy(true);
    setError("");

    try {
      const token = await getToken();
      if (!token) {
        throw new Error("Google sign-in completed, but the Firebase session is not ready. Please try again.");
      }

      const mine = await api.myFarms();
      if (mine.count > 0) {
        localStorage.setItem("fk_farm_id", mine.farms[0].farm_id);
        router.replace(`/farm/${mine.farms[0].farm_id}`);
        return;
      }

      router.replace("/onboarding");
    } catch (err: unknown) {
      // Never convert an API/auth failure into "no farms". Doing so can send
      // an authenticated user into onboarding and hide the real failure.
      navigatingRef.current = false;
      setBusy(false);

      if (err instanceof ApiError) {
        if (err.code === "UNAUTHENTICATED") {
          setError("Google sign-in succeeded, but the backend rejected the Firebase session. Please sign in again.");
          return;
        }
        setError(err.message || "The server could not load your farms. Please try again.");
        return;
      }

      setError(err instanceof Error ? err.message : "Could not finish sign-in. Please try again.");
    }
  }, [router]);

  // Firebase restores an existing session asynchronously. The navigation lock
  // prevents an auth-state callback and the explicit sign-in completion path
  // from both trying to navigate at the same time.
  useEffect(() => {
    const unsubscribe = watchAuth(async (user) => {
      if (user) {
        await routeAfterSignIn();
      }
    });

    return () => unsubscribe();
  }, [routeAfterSignIn]);

  async function handleGoogleSignIn() {
    if (busy || navigatingRef.current) return;
    setBusy(true);
    setError("");

    const err = await signInWithGoogle();
    if (err) {
      setBusy(false);
      setError(err);
      return;
    }

    // signInWithPopup has completed successfully. Route through the same
    // token-validated path; the auth-state callback is safely deduplicated.
    await routeAfterSignIn();
  }

  function useDemoAccount() {
    localStorage.setItem("fk_demo", "true");
    localStorage.setItem("fk_farm_id", "f_demo_01");
    router.push("/farm/f_demo_01");
  }

  const configured = canSignIn();

  return (
    <main className="shell">
      <header className="masthead">
        <div
          className="masthead__wrap"
          style={{ display: "flex", alignItems: "center", gap: 12 }}
        >
          <button
            className="icon-btn"
            onClick={() => router.push("/")}
            aria-label="Back to language"
          >
            <IconArrowLeft size={17} />
          </button>
          <div>
            <h1 className="masthead__title">Fasal Kavach</h1>
            <span className="masthead__rule" />
          </div>
        </div>
      </header>

      <div
        className="sheet"
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          paddingBottom: "var(--sp-5)",
        }}
      >
        <div style={{ marginBottom: "var(--sp-6)" }}>
          <div style={{ color: "var(--paddy)", marginBottom: "var(--sp-3)" }}>
            <IconShield size={30} />
          </div>
          <h2
            className="display"
            style={{ fontSize: "1.6rem", marginBottom: 6 }}
          >
            {t("login.subtitle", lang)}
          </h2>
          <p style={{ color: "var(--ink-2)", fontSize: "0.88rem", lineHeight: 1.6 }}>
            Signing in ties your field to your account, so your alerts follow
            you to a new phone.
          </p>
        </div>

        <div className="section-head">
          <span className="eyebrow">Sign in</span>
          <span className="data" style={{ fontSize: "0.65rem", color: "var(--ink-3)" }}>
            2 / 3
          </span>
        </div>

        <button
          className="btn btn--block"
          onClick={handleGoogleSignIn}
          disabled={!configured || busy || navigatingRef.current}
          style={{
            background: "var(--card)",
            borderColor: "var(--rule)",
            color: "var(--ink)",
            minHeight: 54,
            boxShadow: "var(--lift-1)",
          }}
        >
          {busy ? (
            <span className="spinner" style={{ width: 18, height: 18 }} />
          ) : (
            <IconGoogle size={18} />
          )}
          {busy ? t("login.sending", lang) : t("login.google", lang)}
        </button>

        {error && (
          <div role="alert" className="notice notice--error" style={{ marginTop: "var(--sp-4)" }}>
            {error}
          </div>
        )}

        {!configured && (
          <div className="notice notice--warn" style={{ marginTop: "var(--sp-4)" }}>
            {t("login.notConfigured", lang)}
          </div>
        )}

        {DEMO_MODE && (
          <>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--sp-3)",
                margin: "var(--sp-5) 0",
              }}
            >
              <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
              <span className="eyebrow" style={{ fontSize: "0.6rem" }}>
                or
              </span>
              <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
            </div>

            <button className="btn btn--outline btn--block" onClick={useDemoAccount}>
              {t("login.demo", lang)}
            </button>
            <p
              style={{
                color: "var(--ink-3)",
                fontSize: "0.78rem",
                marginTop: "var(--sp-2)",
                lineHeight: 1.55,
              }}
            >
              {t("login.demoNote", lang)}
            </p>
          </>
        )}
      </div>
    </main>
  );
}
