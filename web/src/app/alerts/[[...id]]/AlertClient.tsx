"use client";
/**
 * Advisory detail — the full warning, what to do, and the evidence
 * behind it.
 *
 * "Why did I get this?" is not a footnote here. A farmer being told to
 * spend money on a spray deserves to see the numbers and the source
 * that triggered it, so the evidence panel shows the same fields the
 * rules engine matched on.
 */
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, type AdvisoryDetail } from "@/lib/api";
import { t, type Lang } from "@/lib/i18n";
import { speak, stopSpeaking, isSpeaking as checkSpeaking } from "@/lib/tts";
import {
  IconArrowLeft,
  IconChevron,
  IconShield,
  IconThumbUp,
  IconThumbDown,
  IconCheck,
} from "@/components/Icons";

function getAdvisoryIdFromUrl(): string {
  if (typeof window === "undefined") return "";
  const parts = window.location.pathname.split("/alerts/");
  return parts[1]?.replace(/\/$/, "") || "";
}

const Bars = () => (
  <span className="bars">
    <i />
    <i />
    <i />
  </span>
);

export default function AlertClient() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("hi");
  const [advisory, setAdvisory] = useState<AdvisoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(false);

  useEffect(() => {
    const s = localStorage.getItem("fk_lang") as Lang | null;
    if (s) setLang(s);
  }, []);

  useEffect(() => {
    const id = getAdvisoryIdFromUrl();
    if (!id) return;
    setLoading(true);
    api
      .advisoryDetail(id)
      .then((d) => {
        setAdvisory(d);
        setError("");
      })
      .catch((e) =>
        setError(e instanceof Error ? e.message : "This advisory could not be loaded.")
      )
      .finally(() => setLoading(false));
  }, []);

  function handleSpeak() {
    if (!advisory) return;
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    speak(advisory.spoken_script || `${advisory.headline}. ${advisory.body}`, lang);
    setSpeaking(true);
    const iv = setInterval(() => {
      if (!checkSpeaking()) {
        setSpeaking(false);
        clearInterval(iv);
      }
    }, 500);
  }

  async function handleFeedback(helpful: boolean) {
    if (!advisory) return;
    setFeedbackSent(true);
    try {
      await api.feedback({
        advisory_id: advisory.advisory_id,
        farm_id: advisory.farm_id,
        helpful,
        acted: helpful,
      });
    } catch {
      /* best effort — never block the farmer on a telemetry write */
    }
  }

  function goBack() {
    stopSpeaking();
    const fid = advisory?.farm_id || localStorage.getItem("fk_farm_id") || "";
    router.push(fid ? `/farm/${fid}` : "/");
  }

  const sev = (s: string) => s.toLowerCase();
  const dateFmt = lang === "en" ? "en-IN" : lang === "bn" ? "bn-IN" : "hi-IN";

  if (loading) {
    return (
      <main className="shell">
        <header className="masthead">
          <div className="masthead__wrap">
            <h1 className="masthead__title">{t("nav.alerts", lang)}</h1>
            <span className="masthead__rule" />
          </div>
        </header>
        <div className="sheet">
          <div className="skeleton" style={{ height: 26, width: "40%", marginBottom: 14 }} />
          <div className="skeleton" style={{ height: 58, marginBottom: 20 }} />
          <div className="skeleton" style={{ height: 128 }} />
        </div>
      </main>
    );
  }

  if (error || !advisory) {
    return (
      <main className="shell">
        <header className="masthead">
          <div className="masthead__wrap" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="icon-btn" onClick={goBack} aria-label="Back">
              <IconArrowLeft size={17} />
            </button>
            <h1 className="masthead__title">{t("nav.alerts", lang)}</h1>
          </div>
        </header>
        <div className="sheet">
          <div role="alert" className="notice notice--error">
            {error || "This advisory is no longer available. It may have expired."}
          </div>
          <button className="btn btn--outline btn--block" onClick={goBack} style={{ marginTop: 20 }}>
            Back to alerts
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="shell">
      <header className="masthead">
        <div className="masthead__wrap" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="icon-btn" onClick={goBack} aria-label="Back to alerts">
            <IconArrowLeft size={17} />
          </button>
          <div>
            <h1 className="masthead__title">{t("nav.alerts", lang)}</h1>
            <span className="masthead__rule" />
          </div>
        </div>
      </header>

      <div className="sheet rise">
        <div className="advisory__top" style={{ marginBottom: 12 }}>
          <span className={`tag tag--${sev(advisory.severity)}`}>
            {t(`severity.${advisory.severity}`, lang)}
          </span>
          {advisory.generated_by === "template" && (
            <span className="tag tag--ghost">{t("template.badge", lang)}</span>
          )}
          <span
            className="data"
            style={{ fontSize: "0.63rem", color: "var(--ink-3)", marginLeft: "auto" }}
          >
            {advisory.rule_id}
          </span>
        </div>

        <h2 className="display" style={{ fontSize: "1.45rem", marginBottom: 8 }}>
          {advisory.headline}
        </h2>

        <p
          className="data"
          style={{
            fontSize: "0.68rem",
            color: "var(--ink-3)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: "var(--sp-5)",
          }}
        >
          {new Date(advisory.created_at).toLocaleDateString(dateFmt, {
            day: "2-digit",
            month: "short",
            year: "numeric",
          })}
        </p>

        <button
          className={`btn btn--block ${speaking ? "btn--solid" : "btn--outline"}`}
          onClick={handleSpeak}
          style={{ marginBottom: "var(--sp-5)" }}
        >
          <Bars />
          {speaking ? t("alert.stop", lang) : t("alert.listen", lang)}
        </button>

        <div className="readout" style={{ marginBottom: "var(--sp-4)" }}>
          <p style={{ lineHeight: 1.8, fontSize: "0.94rem" }}>{advisory.body}</p>
        </div>

        {advisory.actions && advisory.actions.length > 0 && (
          <div className="actions" style={{ marginBottom: "var(--sp-4)" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: "var(--sp-2)",
                color: "var(--paddy-deep)",
              }}
            >
              <IconShield size={16} />
              <span className="eyebrow" style={{ color: "var(--paddy-deep)" }}>
                What to do
              </span>
            </div>
            {/* Numbered because these are a sequence — do the first thing first. */}
            <ol style={{ listStyle: "none" }}>
              {advisory.actions.map((action, i) => (
                <li key={i} className="actions__item">
                  <span className="actions__n">{String(i + 1).padStart(2, "0")}</span>
                  <span>{action}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        <button
          className="btn btn--quiet btn--block"
          onClick={() => setShowEvidence(!showEvidence)}
          aria-expanded={showEvidence}
          style={{ marginBottom: showEvidence ? "var(--sp-3)" : "var(--sp-4)" }}
        >
          <span
            style={{
              display: "inline-flex",
              transform: showEvidence ? "rotate(180deg)" : "none",
              transition: "transform 0.2s ease",
            }}
          >
            <IconChevron size={16} />
          </span>
          {t("alert.why", lang)}
        </button>

        {showEvidence && advisory.evidence && (
          <div className="readout rise" style={{ marginBottom: "var(--sp-4)" }}>
            <div className="section-head" style={{ marginBottom: 6 }}>
              <span className="eyebrow">{t("evidence.title", lang)}</span>
            </div>

            {Object.entries(advisory.evidence).map(([key, value]) => (
              <div key={key} className="readout__row">
                <span className="readout__key">{key.replace(/_/g, " ")}</span>
                <span className="readout__val">{String(value)}</span>
              </div>
            ))}

            {advisory.source_note && (
              <p
                style={{
                  fontSize: "0.78rem",
                  color: "var(--ink-3)",
                  marginTop: "var(--sp-3)",
                  paddingTop: "var(--sp-3)",
                  borderTop: "1px solid var(--rule)",
                  lineHeight: 1.55,
                }}
              >
                <span className="eyebrow" style={{ fontSize: "0.6rem" }}>
                  {t("evidence.source", lang)}
                </span>
                <br />
                {advisory.source_note}
              </p>
            )}

            {advisory.forecast_used && advisory.forecast_used.length > 0 && (
              <div style={{ marginTop: "var(--sp-4)" }}>
                <span className="eyebrow" style={{ fontSize: "0.6rem" }}>
                  {t("evidence.data", lang)}
                </span>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: `repeat(${Math.min(advisory.forecast_used.length, 7)}, 1fr)`,
                    gap: 4,
                    marginTop: 8,
                  }}
                >
                  {advisory.forecast_used.slice(0, 7).map((day) => (
                    <div
                      key={day.date}
                      style={{
                        padding: "7px 3px",
                        border: "1px solid var(--rule)",
                        borderRadius: "var(--r-sm)",
                        textAlign: "center",
                        background: "var(--paper)",
                      }}
                    >
                      <div
                        className="data"
                        style={{ fontSize: "0.58rem", color: "var(--ink-3)" }}
                      >
                        {new Date(day.date).toLocaleDateString("en-IN", {
                          day: "2-digit",
                          month: "short",
                        })}
                      </div>
                      <div
                        className="data"
                        style={{ fontSize: "0.76rem", fontWeight: 600, marginTop: 3 }}
                      >
                        {Math.round(day.t_max_c)}°
                      </div>
                      <div
                        className="data"
                        style={{ fontSize: "0.62rem", color: "var(--monsoon)" }}
                      >
                        {day.rain_mm.toFixed(0)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="readout" style={{ textAlign: "center" }}>
          {feedbackSent ? (
            <p
              style={{
                color: "var(--paddy)",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                fontSize: "0.9rem",
              }}
            >
              <IconCheck size={17} />
              {t("feedback.thanks", lang)}
            </p>
          ) : (
            <>
              <p className="eyebrow" style={{ marginBottom: "var(--sp-3)" }}>
                {t("alert.helpful", lang)}
              </p>
              <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
                <button
                  className="btn btn--outline"
                  onClick={() => handleFeedback(true)}
                  style={{ flex: 1, maxWidth: 140 }}
                >
                  <IconThumbUp size={16} />
                  {t("alert.yes", lang)}
                </button>
                <button
                  className="btn btn--quiet"
                  onClick={() => handleFeedback(false)}
                  style={{ flex: 1, maxWidth: 140 }}
                >
                  <IconThumbDown size={16} />
                  {t("alert.no", lang)}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
