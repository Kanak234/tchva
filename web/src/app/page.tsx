"use client";
/**
 * Landing — pick a language, then sign in.
 *
 * CHANGED: this used to go language -> onboarding, with the farm id
 * kept only in localStorage. That meant no account: a new phone lost
 * the farm, and the backend had no idea who was asking.
 *
 * Now: language -> login -> (existing farm ? farm : onboarding).
 * localStorage is still used, but only as a cache. The source of truth
 * is GET /api/v1/me/farms, keyed on the signed-in account.
 */
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { t, type Lang } from "@/lib/i18n";
import { watchAuth, DEMO_MODE } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("hi");
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const storedLang = localStorage.getItem("fk_lang") as Lang | null;
    if (storedLang) setLang(storedLang);

    // Firebase restores the session asynchronously. Waiting for that
    // before deciding avoids a flash of the language screen for a user
    // who is already signed in.
    const unsub = watchAuth((user) => {
      const storedFarm = localStorage.getItem("fk_farm_id");
      const inDemo = localStorage.getItem("fk_demo") === "true";

      if (user || (inDemo && DEMO_MODE)) {
        router.replace(storedFarm ? `/farm/${storedFarm}` : "/onboarding");
        return;
      }
      if (storedLang) {
        router.replace("/login");
        return;
      }
      setChecking(false); // no language chosen yet — show the picker
    });

    return unsub;
  }, [router]);

  function selectLang(l: Lang) {
    localStorage.setItem("fk_lang", l);
    setLang(l);
    router.push("/login");
  }

  if (checking) {
    return (
      <main
        style={{
          minHeight: "100dvh",
          display: "grid",
          placeItems: "center",
          background: "var(--surface-alt)",
        }}
      >
        <div style={{ fontSize: "2rem" }}>🌾</div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: "100dvh", background: "var(--surface-alt)", display: "flex", flexDirection: "column" }}>
      <div className="top-header" style={{ textAlign: "center", padding: "32px 24px 24px" }}>
        <div style={{ fontSize: "2.5rem", marginBottom: "8px" }}>🌾</div>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 800, color: "white", margin: 0 }}>Fasal Kavach</h1>
        <p style={{ color: "rgba(255,255,255,0.8)", fontSize: "0.9rem", marginTop: "4px" }}>
          AI Climate Early-Warning for Farmers
        </p>
      </div>

      <div style={{ flex: 1, padding: "32px 24px" }}>
        <p style={{ textAlign: "center", color: "var(--text-secondary)", marginBottom: "24px", fontWeight: 600 }}>
          {t("lang.select", lang)}
        </p>
        <div className="lang-grid" style={{ maxWidth: "360px", margin: "0 auto" }}>
          {([["hi", "हिंदी", "Hindi"], ["en", "English", "English"], ["kho", "खोरठा", "Khortha"], ["bn", "বাংলা", "Bengali"]] as [Lang, string, string][]).map(
            ([code, native, name]) => (
              <button key={code} className="lang-btn fade-in" onClick={() => selectLang(code)}>
                <span style={{ fontSize: "1.4rem", fontWeight: 700 }}>{native}</span>
                <span className="lang-name">{name}</span>
              </button>
            )
          )}
        </div>
      </div>
    </main>
  );
}
