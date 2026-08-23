"use client";
/**
 * Farm dashboard — three tabs: what's wrong, ask a question, field record.
 *
 * The Risk Horizon sits above the alert list because the shape of the
 * week is the thing a farmer wants first. The alerts explain it.
 */
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, type Farm, type Advisory, type WeatherForecast } from "@/lib/api";
import { t, type Lang } from "@/lib/i18n";
import { speak, stopSpeaking, isSpeaking as checkSpeaking } from "@/lib/tts";
import { signOutUser } from "@/lib/auth";
import RiskHorizon from "@/components/RiskHorizon";
import {
  IconAlert,
  IconAsk,
  IconCrop,
  IconCheck,
  IconRefresh,
  IconSend,
  IconSignOut,
} from "@/components/Icons";

function getFarmIdFromUrl(): string {
  if (typeof window === "undefined") return "";
  const parts = window.location.pathname.split("/farm/");
  return parts[1]?.replace(/\/$/, "") || "";
}

const SEV_ORDER: Record<string, number> = { SEVERE: 0, MODERATE: 1, LOW: 2 };

/** Three animated strokes — the listen button's state, without emoji. */
const Bars = () => (
  <span className="bars">
    <i />
    <i />
    <i />
  </span>
);

export default function FarmClient() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("hi");
  const [farmId, setFarmId] = useState("");
  const [farm, setFarm] = useState<Farm | null>(null);
  const [advisories, setAdvisories] = useState<Advisory[]>([]);
  const [weather, setWeather] = useState<WeatherForecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const [tab, setTab] = useState<"alerts" | "ask" | "farm">("alerts");
  const [question, setQuestion] = useState("");
  const [askResult, setAskResult] = useState<{
    answer_text: string;
    spoken_script: string;
    grounded: boolean;
  } | null>(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("fk_lang") as Lang | null;
    if (stored) setLang(stored);
    const id = getFarmIdFromUrl() || localStorage.getItem("fk_farm_id") || "";
    if (!id) {
      router.replace("/");
      return;
    }
    setFarmId(id);
  }, [router]);

  const loadData = useCallback(
    async (silent = false) => {
      if (!farmId) return;
      if (!silent) setLoading(true);
      setError("");
      try {
        const [farmData, advisoryData] = await Promise.all([
          api.getFarm(farmId),
          api.advisories(farmId, lang),
        ]);
        setFarm(farmData);
        setAdvisories(
          advisoryData.advisories.sort(
            (a, b) =>
              (SEV_ORDER[a.severity] ?? 3) - (SEV_ORDER[b.severity] ?? 3) ||
              new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          )
        );
        if (farmData.grid_id) {
          setWeather(await api.weather(farmData.grid_id).catch(() => null));
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Could not reach the advisory service. Refresh when you have signal."
        );
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [farmId, lang]
  );

  useEffect(() => {
    loadData(false);
    const iv = setInterval(() => loadData(true), 30000);
    return () => clearInterval(iv);
  }, [loadData]);

  function handleSpeak(adv: Advisory) {
    if (speakingId === adv.advisory_id) {
      stopSpeaking();
      setSpeakingId(null);
      return;
    }
    stopSpeaking();
    speak(adv.spoken_script || `${adv.headline}. ${adv.body}`, lang);
    setSpeakingId(adv.advisory_id);
    const iv = setInterval(() => {
      if (!checkSpeaking()) {
        setSpeakingId(null);
        clearInterval(iv);
      }
    }, 500);
  }

  async function handleAsk() {
    if (!question.trim() || !farmId) return;
    setAsking(true);
    setAskResult(null);
    try {
      setAskResult(
        await api.ask({ farm_id: farmId, question: question.trim(), language: lang })
      );
    } catch (err) {
      setAskResult({
        answer_text:
          err instanceof Error
            ? err.message
            : "That question could not be answered right now. Try again in a moment.",
        spoken_script: "",
        grounded: false,
      });
    } finally {
      setAsking(false);
    }
  }

  async function handleSignOut() {
    await signOutUser();
    localStorage.removeItem("fk_demo");
    router.replace("/");
  }

  const sev = (s: string) => s.toLowerCase();
  const dateFmt = lang === "en" ? "en-IN" : lang === "bn" ? "bn-IN" : "hi-IN";

  // First paint: skeleton, not a spinner. Shows the shape that's coming.
  if (loading && !farm) {
    return (
      <main className="shell">
        <header className="masthead">
          <div className="masthead__wrap">
            <h1 className="masthead__title">Fasal Kavach</h1>
            <span className="masthead__rule" />
          </div>
        </header>
        <div className="sheet">
          <div className="skeleton" style={{ height: 168, marginBottom: 20 }} />
          <div className="skeleton" style={{ height: 118, marginBottom: 12 }} />
          <div className="skeleton" style={{ height: 118 }} />
        </div>
      </main>
    );
  }

  return (
    <main className="shell">
      <header className="masthead">
        <div className="masthead__wrap">
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            <div>
              <h1 className="masthead__title">{t("app.name", lang)}</h1>
              <span className="masthead__rule" />
            </div>
            <button
              className="icon-btn"
              onClick={handleSignOut}
              aria-label={t("login.signOut", lang)}
            >
              <IconSignOut size={16} />
            </button>
          </div>

          {farm && (
            <div className="fieldline">
              <span>{farm.village}</span>
              <span className="fieldline__sep">/</span>
              <span>{t(`crop.${farm.crop}`, lang)}</span>
              <span className="fieldline__sep">/</span>
              <span>
                <span className="fieldline__key">HA </span>
                {farm.area_ha}
              </span>
              <span className="fieldline__sep">/</span>
              <span>
                <span className="fieldline__key">DAS </span>
                {farm.days_after_sowing}
              </span>
              <span className="fieldline__sep">/</span>
              <span style={{ textTransform: "uppercase" }}>{farm.growth_stage}</span>
            </div>
          )}
        </div>
      </header>

      {error && (
        <div style={{ maxWidth: 560, margin: "0 auto", width: "100%", padding: "12px 16px 0" }}>
          <div role="alert" className="notice notice--error">
            {error}
          </div>
        </div>
      )}

      <div className="sheet">
        {tab === "alerts" && (
          <>
            {/* Say it before the risk strip, not after. Everything below
                this line — the horizon and every advisory under it — is
                derived from the same forecast window. */}
            {weather?.has_synthetic_data && (
              <div
                role="alert"
                className="notice notice--warn rise"
                style={{ marginBottom: "var(--sp-4)" }}
              >
                {t("weather.synthetic", lang)}
              </div>
            )}

            {weather && weather.forecast.length > 0 && farm && (
              <div style={{ marginBottom: "var(--sp-5)" }}>
                <RiskHorizon forecast={weather.forecast} crop={farm.crop} lang={lang} />
              </div>
            )}

            <div className="section-head">
              <span className="eyebrow">{t("nav.alerts", lang)}</span>
              <span className="data" style={{ fontSize: "0.65rem", color: "var(--ink-3)" }}>
                {String(advisories.length).padStart(2, "0")}
              </span>
            </div>

            {advisories.length === 0 && !loading && (
              <div className="empty rise">
                <div className="empty__mark">
                  <IconCheck size={20} />
                </div>
                <h3 className="display" style={{ fontSize: "1.05rem", marginBottom: 6 }}>
                  {t("empty.title", lang)}
                </h3>
                <p style={{ color: "var(--ink-2)", fontSize: "0.86rem", lineHeight: 1.6 }}>
                  {t("empty.body", lang)}
                </p>
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {advisories.map((adv, i) => (
                <button
                  key={adv.advisory_id}
                  className={`advisory advisory--${sev(adv.severity)} ${
                    !adv.read ? "advisory--unread" : ""
                  } rise`}
                  style={{ animationDelay: `${i * 60}ms` }}
                  onClick={() => router.push(`/alerts/${adv.advisory_id}`)}
                >
                  <div className="advisory__top">
                    <span className={`tag tag--${sev(adv.severity)}`}>
                      {t(`severity.${adv.severity}`, lang)}
                    </span>
                    {adv.generated_by === "template" && (
                      <span className="tag tag--ghost">{t("template.badge", lang)}</span>
                    )}
                  </div>

                  <h3 className="advisory__headline">{adv.headline}</h3>
                  <p className="advisory__body">
                    {adv.body.length > 128 ? adv.body.slice(0, 128) + "…" : adv.body}
                  </p>

                  <div className="advisory__foot">
                    <span className="advisory__stamp">
                      {new Date(adv.created_at).toLocaleDateString(dateFmt, {
                        day: "2-digit",
                        month: "short",
                      })}
                    </span>
                    <span
                      role="button"
                      tabIndex={0}
                      className={`listen ${speakingId === adv.advisory_id ? "listen--on" : ""}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSpeak(adv);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          e.stopPropagation();
                          handleSpeak(adv);
                        }
                      }}
                    >
                      <Bars />
                      {speakingId === adv.advisory_id
                        ? t("alert.stop", lang)
                        : t("alert.listen", lang)}
                    </span>
                  </div>
                </button>
              ))}
            </div>

            <button
              className="btn btn--quiet btn--block"
              onClick={() => loadData(false)}
              disabled={loading}
              style={{ marginTop: "var(--sp-4)" }}
            >
              {loading ? (
                <span className="spinner" style={{ width: 17, height: 17 }} />
              ) : (
                <IconRefresh size={16} />
              )}
              Refresh
            </button>
          </>
        )}

        {tab === "ask" && (
          <div className="rise">
            <div className="section-head">
              <span className="eyebrow">{t("ask.title", lang)}</span>
            </div>

            <p
              style={{
                color: "var(--ink-2)",
                fontSize: "0.86rem",
                lineHeight: 1.6,
                marginBottom: "var(--sp-4)",
              }}
            >
              {t("ask.subtitle", lang)}
            </p>

            {askResult && (
              <div className="readout rise" style={{ marginBottom: "var(--sp-4)" }}>
                <p style={{ lineHeight: 1.75, fontSize: "0.92rem" }}>{askResult.answer_text}</p>

                {!askResult.grounded && (
                  <div className="notice notice--warn" style={{ marginTop: "var(--sp-3)" }}>
                    {t("ask.ungrounded", lang)}
                  </div>
                )}

                {askResult.spoken_script && (
                  <button
                    className="listen"
                    onClick={() => speak(askResult.spoken_script, lang)}
                    style={{ marginTop: "var(--sp-3)" }}
                  >
                    <Bars />
                    {t("alert.listen", lang)}
                  </button>
                )}
              </div>
            )}

            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                className="input"
                placeholder={t("ask.type", lang)}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAsk()}
                disabled={asking}
                aria-label={t("ask.type", lang)}
              />
              <button
                className="btn btn--solid"
                onClick={handleAsk}
                disabled={asking || !question.trim()}
                style={{ minWidth: 58, padding: "0 18px" }}
                aria-label={t("ask.send", lang)}
              >
                {asking ? (
                  <span className="spinner spinner--light" style={{ width: 17, height: 17 }} />
                ) : (
                  <IconSend size={17} />
                )}
              </button>
            </div>
          </div>
        )}

        {tab === "farm" && farm && (
          <div className="rise">
            <div className="section-head">
              <span className="eyebrow">{t("nav.farm", lang)}</span>
              <span className="data" style={{ fontSize: "0.63rem", color: "var(--ink-3)" }}>
                {farm.farm_id}
              </span>
            </div>

            <div className="readout">
              {(
                [
                  [t("onboarding.village", lang), farm.village],
                  [t("onboarding.crop", lang), t(`crop.${farm.crop}`, lang)],
                  [
                    t("onboarding.sowing", lang),
                    new Date(farm.sowing_date).toLocaleDateString(dateFmt, {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    }),
                  ],
                  [t("onboarding.area", lang), `${farm.area_ha} ha`],
                  [t("onboarding.irrigation", lang), t(`irrigation.${farm.irrigation}`, lang)],
                  ["Growth stage", farm.growth_stage],
                  ["Days after sowing", String(farm.days_after_sowing)],
                  ["Grid cell", farm.grid_id],
                ] as [string, string][]
              ).map(([key, val]) => (
                <div key={key} className="readout__row">
                  <span className="readout__key">{key}</span>
                  <span className="readout__val">{val}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <nav className="tabbar" aria-label="Sections">
        <button
          className={`tab ${tab === "alerts" ? "tab--on" : ""}`}
          onClick={() => setTab("alerts")}
        >
          <IconAlert />
          {t("nav.alerts", lang)}
        </button>
        <button className={`tab ${tab === "ask" ? "tab--on" : ""}`} onClick={() => setTab("ask")}>
          <IconAsk />
          {t("nav.ask", lang)}
        </button>
        <button className={`tab ${tab === "farm" ? "tab--on" : ""}`} onClick={() => setTab("farm")}>
          <IconCrop />
          {t("nav.farm", lang)}
        </button>
      </nav>
    </main>
  );
}
