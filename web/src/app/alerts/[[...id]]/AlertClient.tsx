"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, type AdvisoryDetail } from "@/lib/api";
import { t, type Lang } from "@/lib/i18n";
import { speak, stopSpeaking, isSpeaking as checkSpeaking } from "@/lib/tts";

function getAdvisoryIdFromUrl(): string {
  if (typeof window === "undefined") return "";
  const parts = window.location.pathname.split("/alerts/");
  return parts[1]?.replace(/\/$/, "") || "";
}

export default function AlertClient() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("hi");
  const [advisory, setAdvisory] = useState<AdvisoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(false);

  useEffect(() => { const s = localStorage.getItem("fk_lang") as Lang | null; if (s) setLang(s); }, []);

  useEffect(() => {
    const id = getAdvisoryIdFromUrl();
    if (!id) return;
    setLoading(true);
    api.advisoryDetail(id).then(d => { setAdvisory(d); setError(""); }).catch(e => setError(e instanceof Error ? e.message : "Failed to load")).finally(() => setLoading(false));
  }, []);

  function handleSpeak() {
    if (!advisory) return;
    if (speaking) { stopSpeaking(); setSpeaking(false); return; }
    speak(advisory.spoken_script || `${advisory.headline}. ${advisory.body}`, lang);
    setSpeaking(true);
    const iv = setInterval(() => { if (!checkSpeaking()) { setSpeaking(false); clearInterval(iv); } }, 500);
  }

  async function handleFeedback(helpful: boolean) {
    if (!advisory) return;
    setFeedbackSent(true);
    try { await api.feedback({ advisory_id: advisory.advisory_id, farm_id: advisory.farm_id, helpful, acted: helpful }); } catch { /* best effort */ }
  }

  const sev = (s: string) => s.toLowerCase();

  if (loading) return (
    <main style={{ minHeight: "100dvh", display: "grid", placeItems: "center", background: "var(--surface-alt)" }}>
      <div style={{ textAlign: "center" }}><div className="spinner" style={{ margin: "0 auto 16px" }} /><p style={{ color: "var(--text-secondary)" }}>Loading...</p></div>
    </main>
  );

  if (error || !advisory) return (
    <main style={{ minHeight: "100dvh", background: "var(--surface-alt)" }}>
      <div className="top-header"><button onClick={() => router.back()} style={{ background: "none", border: "none", color: "white", fontSize: "1.1rem", cursor: "pointer", fontWeight: 600 }}>← Back</button></div>
      <div style={{ padding: 24, textAlign: "center", color: "var(--severe)" }}><p>{error || "Advisory not found"}</p></div>
    </main>
  );

  return (
    <main style={{ minHeight: "100dvh", background: "var(--surface-alt)" }}>
      <div className="top-header">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => { stopSpeaking(); const fid = advisory.farm_id || localStorage.getItem("fk_farm_id") || ""; router.push(fid ? `/farm/${fid}` : "/"); }} style={{ background: "rgba(255,255,255,0.15)", border: "none", color: "white", width: 36, height: 36, borderRadius: 8, fontSize: "1.1rem", cursor: "pointer", display: "grid", placeItems: "center" }}>←</button>
          <h1 style={{ fontSize: "1rem", fontWeight: 700, margin: 0 }}>{t("nav.alerts", lang)}</h1>
        </div>
      </div>

      <div className="page-content slide-up" style={{ paddingBottom: 40 }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <span className={`severity-badge ${sev(advisory.severity)}`}>{t(`severity.${advisory.severity}`, lang)}</span>
            {advisory.generated_by === "template" && <span className="template-badge">{t("template.badge", lang)}</span>}
          </div>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 800, lineHeight: 1.4 }}>{advisory.headline}</h2>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 4 }}>{new Date(advisory.created_at).toLocaleDateString(lang === "en" ? "en-IN" : "hi-IN", { day: "numeric", month: "long", year: "numeric" })}</p>
        </div>

        <button className={`speak-btn ${speaking ? "speaking" : ""}`} onClick={handleSpeak} style={{ width: "100%", marginBottom: 20, padding: "14px" }}>
          {speaking ? `🔊 ${t("alert.stop", lang)}` : `🔈 ${t("alert.listen", lang)}`}
        </button>

        <div style={{ background: "var(--surface)", borderRadius: "var(--radius-card)", boxShadow: "var(--shadow-card)", padding: 20, marginBottom: 16 }}>
          <p style={{ lineHeight: 1.8, fontSize: "0.95rem" }}>{advisory.body}</p>
        </div>

        {advisory.actions && advisory.actions.length > 0 && (
          <div style={{ background: "var(--accent-bg)", borderRadius: "var(--radius-card)", padding: 20, marginBottom: 16, border: "1px solid var(--low-border)" }}>
            <h3 style={{ fontWeight: 700, fontSize: "0.95rem", marginBottom: 12, color: "var(--accent)" }}>🛡️ What to do</h3>
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
              {advisory.actions.map((action, i) => (
                <li key={i} style={{ display: "flex", gap: 10, fontSize: "0.9rem", lineHeight: 1.5 }}>
                  <span style={{ fontWeight: 700, color: "var(--accent)", flexShrink: 0 }}>{i + 1}.</span><span>{action}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <button className="btn-secondary" onClick={() => setShowEvidence(!showEvidence)} style={{ width: "100%", marginBottom: 12 }}>
          {showEvidence ? "▲" : "▼"} {t("alert.why", lang)}
        </button>

        {showEvidence && advisory.evidence && (
          <div className="evidence-panel slide-up" style={{ marginBottom: 16 }}>
            <h3 style={{ fontWeight: 700, fontSize: "0.9rem", marginBottom: 12 }}>{t("evidence.title", lang)}</h3>
            {Object.entries(advisory.evidence).map(([key, value]) => (
              <div key={key} className="evidence-row"><span className="evidence-label">{key.replace(/_/g, " ")}</span><span className="evidence-value">{String(value)}</span></div>
            ))}
            {advisory.source_note && <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 12 }}>📊 {t("evidence.source", lang)}: {advisory.source_note}</p>}
            {advisory.forecast_used && advisory.forecast_used.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <p style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>{t("evidence.data", lang)}</p>
                <div style={{ display: "flex", gap: 6, overflowX: "auto" }}>
                  {advisory.forecast_used.map(day => (
                    <div key={day.date} style={{ minWidth: 64, padding: "8px 6px", background: "var(--surface)", borderRadius: 8, textAlign: "center", fontSize: "0.72rem", border: "1px solid #E0E5E0" }}>
                      <div style={{ fontWeight: 600 }}>{new Date(day.date).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</div>
                      <div style={{ fontWeight: 700, marginTop: 2 }}>{Math.round(day.t_max_c)}°C</div>
                      <div style={{ color: "#2E7D87", fontWeight: 600 }}>{day.rain_mm.toFixed(1)}mm</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div style={{ background: "var(--surface)", borderRadius: "var(--radius-card)", boxShadow: "var(--shadow-card)", padding: 20, textAlign: "center" }}>
          {feedbackSent ? <p style={{ color: "var(--accent)", fontWeight: 600 }}>✓ {t("feedback.thanks", lang)}</p> : <>
            <p style={{ fontWeight: 600, marginBottom: 12 }}>{t("alert.helpful", lang)}</p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button className="btn-primary" onClick={() => handleFeedback(true)} style={{ flex: 1, maxWidth: 120 }}>👍 {t("alert.yes", lang)}</button>
              <button className="btn-secondary" onClick={() => handleFeedback(false)} style={{ flex: 1, maxWidth: 120 }}>👎 {t("alert.no", lang)}</button>
            </div>
          </>}
        </div>
      </div>
    </main>
  );
}
