"use client";
/**
 * Landing — pick a language, then sign in.
 *
 * Flow: language -> login -> (existing farm ? farm : onboarding).
 * localStorage caches the choice; the source of truth for which farm
 * belongs to you is GET /api/v1/me/farms, keyed on the account.
 */
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { t, type Lang } from "@/lib/i18n";
import { watchAuth, DEMO_MODE } from "@/lib/auth";
import { IconShield } from "@/components/Icons";

const LANGS: [Lang, string, string][] = [
  ["hi", "हिंदी", "Hindi"],
  ["en", "English", "English"],
  ["kho", "खोरठा", "Khortha"],
  ["bn", "বাংলা", "Bengali"],
];

export default function HomePage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("hi");
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const storedLang = localStorage.getItem("fk_lang") as Lang | null;
    if (storedLang) setLang(storedLang);

    // Firebase restores the session asynchronously. Waiting for it before
    // deciding avoids flashing the language picker at a signed-in user.
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
      setChecking(false);
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
      <main className="shell" style={{ display: "grid", placeItems: "center" }}>
        <div style={{ color: "var(--paddy)", opacity: 0.5 }}>
          <IconShield size={38} />
        </div>
      </main>
    );
  }

  return (
    <main className="shell">
      <header className="masthead" style={{ paddingBottom: 22 }}>
        <div className="masthead__wrap">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ color: "var(--paddy)" }}>
              <IconShield size={24} />
            </span>
            <h1 className="masthead__title" style={{ fontSize: "1.3rem" }}>
              Fasal Kavach
            </h1>
          </div>
          <span className="masthead__rule" />
          <p
            className="data"
            style={{
              fontSize: "0.68rem",
              color: "rgba(239,240,233,0.62)",
              marginTop: 10,
              letterSpacing: "0.04em",
            }}
          >
            CLIMATE EARLY-WARNING · SMALLHOLDER FARMS
          </p>
        </div>
      </header>

      <div
        className="sheet"
        style={{
          paddingBottom: "var(--sp-5)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        <div className="section-head">
          <span className="eyebrow">{t("lang.select", lang)}</span>
          <span className="data" style={{ fontSize: "0.65rem", color: "var(--ink-3)" }}>
            1 / 3
          </span>
        </div>

        <div className="langgrid">
          {LANGS.map(([code, native, latin], i) => (
            <button
              key={code}
              className="langbtn rise"
              style={{ animationDelay: `${i * 60}ms` }}
              onClick={() => selectLang(code)}
              lang={code === "kho" ? "hi" : code}
            >
              <span className="langbtn__native">{native}</span>
              <span className="langbtn__latin">{latin}</span>
            </button>
          ))}
        </div>

        <p
          style={{
            marginTop: "var(--sp-5)",
            fontSize: "0.8rem",
            color: "var(--ink-3)",
            lineHeight: 1.6,
          }}
        >
          Warnings, spoken scripts and crop advice all arrive in the language you
          pick here. You can change it later.
        </p>
      </div>
    </main>
  );
}
