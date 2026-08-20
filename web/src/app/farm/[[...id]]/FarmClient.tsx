"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, type Farm, type Advisory, type WeatherForecast } from "@/lib/api";
import { t, type Lang } from "@/lib/i18n";
import { speak, stopSpeaking, isSpeaking as checkSpeaking } from "@/lib/tts";
import { signOutUser } from "@/lib/auth";

function getFarmIdFromUrl(): string {
  if (typeof window === "undefined") return "";
  const parts = window.location.pathname.split("/farm/");
  return parts[1]?.replace(/\/$/, "") || "";
}

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
  const [askResult, setAskResult] = useState<{ answer_text: string; spoken_script: string; grounded: boolean } | null>(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("fk_lang") as Lang | null;
    if (stored) setLang(stored);
    const id = getFarmIdFromUrl() || localStorage.getItem("fk_farm_id") || "";
    if (!id) { router.replace("/"); return; }
    setFarmId(id);
  }, [router]);

  const loadData = useCallback(async (silent = false) => {
    if (!farmId) return;
    if (!silent) {
      setLoading(true);
    }
    setError("");
    try {
      const [farmData, advisoryData] = await Promise.all([api.getFarm(farmId), api.advisories(farmId, lang)]);
      setFarm(farmData);
      const order: Record<string, number> = { SEVERE: 0, MODERATE: 1, LOW: 2 };
      setAdvisories(advisoryData.advisories.sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3) || new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
      if (farmData.grid_id) setWeather(await api.weather(farmData.grid_id).catch(() => null));
    } catch (err) { 
      setError(err instanceof Error ? err.message : "Failed to load"); 
    } finally { 
      if (!silent) {
        setLoading(false); 
      }
    }
  }, [farmId, lang]);

  useEffect(() => {
    loadData(false);
    // Background polling every 30 seconds to automatically update real-time data
    const iv = setInterval(() => {
      loadData(true);
    }, 30000);
    return () => clearInterval(iv);
  }, [loadData]);

  function handleSpeak(adv: Advisory) {
    if (speakingId === adv.advisory_id) { stopSpeaking(); setSpeakingId(null); return; }
    stopSpeaking();
    speak(adv.spoken_script || `${adv.headline}. ${adv.body}`, lang);
    setSpeakingId(adv.advisory_id);
    const iv = setInterval(() => { if (!checkSpeaking()) { setSpeakingId(null); clearInterval(iv); } }, 500);
  }

  async function handleAsk() {
    if (!question.trim() || !farmId) return;
    setAsking(true); setAskResult(null);
    try { setAskResult(await api.ask({ farm_id: farmId, question: question.trim(), language: lang })); }
    catch (err) { setAskResult({ answer_text: err instanceof Error ? err.message : "Error", spoken_script: "", grounded: false }); }
    finally { setAsking(false); }
  }

  async function handleSignOut() { await signOutUser(); localStorage.removeItem("fk_demo"); router.replace("/"); }
  const sev = (s: string) => s.toLowerCase();

  if (loading && !farm) return (
    <main style={{ minHeight: "100dvh", display: "grid", placeItems: "center", background: "var(--surface-alt)" }}>
      <div style={{ textAlign: "center" }}><div className="spinner" style={{ margin: "0 auto 16px" }} /><p style={{ color: "var(--text-secondary)" }}>Loading...</p></div>
    </main>
  );

  return (
    <main style={{ minHeight: "100dvh", background: "var(--surface-alt)" }}>
      <div className="top-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h1 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0 }}>🌾 {t("app.name", lang)}</h1>
            <p style={{ fontSize: "0.8rem", opacity: 0.85, marginTop: 2 }}>{t("app.tagline", lang)}</p>
          </div>
          <button onClick={handleSignOut} style={{ background: "rgba(255,255,255,0.15)", border: "1px solid rgba(255,255,255,0.3)", color: "white", padding: "6px 14px", borderRadius: 8, fontSize: "0.8rem", fontWeight: 600, cursor: "pointer" }}>{t("login.signOut", lang)}</button>
        </div>
        {farm && <div style={{ marginTop: 12, display: "flex", gap: 16, fontSize: "0.82rem", opacity: 0.9, flexWrap: "wrap" }}>
          <span>📍 {farm.village}</span><span>🌱 {t(`crop.${farm.crop}`, lang)}</span><span>📐 {farm.area_ha} ha</span><span>🌿 {farm.growth_stage}</span>
        </div>}
      </div>

      {error && <div style={{ background: "var(--severe-bg)", color: "var(--severe)", padding: "12px 16px", fontSize: "0.9rem", textAlign: "center" }}>{error}</div>}

      <div className="page-content">
        {tab === "alerts" && <>
          {weather && weather.forecast.length > 0 && <div className="fade-in" style={{ marginBottom: 20 }}>
            <p style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>{t("forecast.updated", lang)}</p>
            <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4 }}>
              {weather.forecast.slice(0, 5).map(day => (
                <div key={day.date} style={{ minWidth: 72, padding: "10px 8px", background: "var(--surface)", borderRadius: 12, textAlign: "center", boxShadow: "var(--shadow-card)", fontSize: "0.78rem" }}>
                  <div style={{ fontWeight: 600, color: "var(--text-secondary)" }}>{new Date(day.date).toLocaleDateString(lang === "en" ? "en-IN" : "hi-IN", { weekday: "short" })}</div>
                  <div style={{ fontSize: "1.1rem", margin: "4px 0" }}>{day.rain_mm > 5 ? "🌧️" : day.rain_mm > 0 ? "🌦️" : day.t_max_c > 38 ? "🔥" : "☀️"}</div>
                  <div style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{Math.round(day.t_max_c)}° / {Math.round(day.t_min_c)}°</div>
                  {day.rain_mm > 0 && <div style={{ color: "#2E7D87", fontWeight: 600, fontSize: "0.7rem" }}>{day.rain_mm.toFixed(1)} mm</div>}
                </div>
              ))}
            </div>
          </div>}

          {advisories.length === 0 && !loading && <div className="empty-state fade-in">
            <div style={{ fontSize: "3rem", marginBottom: 16 }}>✅</div>
            <h2 style={{ fontWeight: 700, marginBottom: 8 }}>{t("empty.title", lang)}</h2>
            <p>{t("empty.body", lang)}</p>
          </div>}

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {advisories.map((adv, i) => (
              <div key={adv.advisory_id} className={`alert-card ${sev(adv.severity)} ${!adv.read ? "unread" : ""} slide-up`} style={{ animationDelay: `${i * 0.08}s` }} onClick={() => router.push(`/alerts/${adv.advisory_id}`)}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span className={`severity-badge ${sev(adv.severity)}`}>{t(`severity.${adv.severity}`, lang)}</span>
                  {adv.generated_by === "template" && <span className="template-badge">{t("template.badge", lang)}</span>}
                </div>
                <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: 6, lineHeight: 1.4 }}>{adv.headline}</h3>
                <p style={{ fontSize: "0.88rem", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: 10 }}>{adv.body.length > 120 ? adv.body.slice(0, 120) + "…" : adv.body}</p>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{new Date(adv.created_at).toLocaleDateString(lang === "en" ? "en-IN" : "hi-IN", { day: "numeric", month: "short" })}</span>
                  <button className={`speak-btn ${speakingId === adv.advisory_id ? "speaking" : ""}`} onClick={e => { e.stopPropagation(); handleSpeak(adv); }} style={{ padding: "6px 12px", minHeight: 36, fontSize: "0.8rem" }}>
                    {speakingId === adv.advisory_id ? `🔊 ${t("alert.stop", lang)}` : `🔈 ${t("alert.listen", lang)}`}
                  </button>
                </div>
              </div>
            ))}
          </div>
          <button className="btn-secondary fade-in" onClick={() => loadData(false)} disabled={loading} style={{ width: "100%", marginTop: 20 }}>{loading ? <span className="spinner" style={{ width: 20, height: 20 }} /> : "↻ Refresh"}</button>
        </>}

        {tab === "ask" && <div className="fade-in">
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <h2 style={{ fontSize: "1.3rem", fontWeight: 700 }}>{t("ask.title", lang)}</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>{t("ask.subtitle", lang)}</p>
          </div>
          {askResult && <div className="slide-up" style={{ background: "var(--surface)", padding: 20, borderRadius: "var(--radius-card)", boxShadow: "var(--shadow-card)", marginBottom: 20 }}>
            <p style={{ lineHeight: 1.7, fontSize: "0.95rem" }}>{askResult.answer_text}</p>
            {!askResult.grounded && <p style={{ marginTop: 12, fontSize: "0.8rem", color: "var(--moderate)", background: "var(--moderate-bg)", padding: "8px 12px", borderRadius: 8 }}>⚠️ {t("ask.ungrounded", lang)}</p>}
            {askResult.spoken_script && <button className="speak-btn" onClick={() => speak(askResult.spoken_script, lang)} style={{ marginTop: 12 }}>🔈 {t("alert.listen", lang)}</button>}
          </div>}
          <div style={{ display: "flex", gap: 8 }}>
            <input type="text" className="form-input" placeholder={t("ask.type", lang)} value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => e.key === "Enter" && handleAsk()} disabled={asking} />
            <button className="btn-primary" onClick={handleAsk} disabled={asking || !question.trim()} style={{ minWidth: 64 }}>{asking ? <span className="spinner" style={{ width: 18, height: 18, borderTopColor: "white" }} /> : t("ask.send", lang)}</button>
          </div>
        </div>}

        {tab === "farm" && farm && <div className="fade-in">
          <div style={{ background: "var(--surface)", borderRadius: "var(--radius-card)", boxShadow: "var(--shadow-card)", padding: 20 }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: 16 }}>{t("nav.farm", lang)}</h2>
            {([
              [t("onboarding.village", lang), farm.village],
              [t("onboarding.crop", lang), t(`crop.${farm.crop}`, lang)],
              [t("onboarding.sowing", lang), new Date(farm.sowing_date).toLocaleDateString(lang === "en" ? "en-IN" : "hi-IN")],
              [t("onboarding.area", lang), `${farm.area_ha} ha`],
              [t("onboarding.irrigation", lang), t(`irrigation.${farm.irrigation}`, lang)],
              ["Growth Stage", farm.growth_stage],
              ["Days After Sowing", `${farm.days_after_sowing}`],
            ] as [string, string][]).map(([label, value]) => (
              <div key={label} className="evidence-row"><span className="evidence-label">{label}</span><span className="evidence-value">{value}</span></div>
            ))}
          </div>
        </div>}
      </div>

      <nav className="nav-bar">
        <button className={`nav-item ${tab === "alerts" ? "active" : ""}`} onClick={() => setTab("alerts")}><span style={{ fontSize: "1.3rem" }}>⚠️</span><span>{t("nav.alerts", lang)}</span></button>
        <button className={`nav-item ${tab === "ask" ? "active" : ""}`} onClick={() => setTab("ask")}><span style={{ fontSize: "1.3rem" }}>💬</span><span>{t("nav.ask", lang)}</span></button>
        <button className={`nav-item ${tab === "farm" ? "active" : ""}`} onClick={() => setTab("farm")}><span style={{ fontSize: "1.3rem" }}>🌾</span><span>{t("nav.farm", lang)}</span></button>
      </nav>
    </main>
  );
}
