"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { t, type Lang } from "@/lib/i18n";

const CROPS = ["paddy", "maize", "wheat", "tomato"] as const;
const IRRIGATIONS = ["rainfed", "canal", "borewell", "mixed"] as const;

// Hazaribagh district grid cell centers
const GRID_CELLS = [
  { name: "Barhi / Hazaribagh NW", lat: 24.00, lon: 85.25 },
  { name: "Daru / Hazaribagh NE", lat: 24.00, lon: 85.50 },
  { name: "Keredari / Hazaribagh SW", lat: 23.75, lon: 85.25 },
  { name: "Ichak / Hazaribagh SE", lat: 23.75, lon: 85.50 },
];

export default function OnboardingPage() {
  const router = useRouter();
  const lang = (typeof window !== "undefined" ? localStorage.getItem("fk_lang") : "hi") as Lang || "hi";

  const [form, setForm] = useState({
    village: "",
    location: GRID_CELLS[0],
    crop: "paddy" as typeof CROPS[number],
    sowing_date: "",
    area_ha: "",
    irrigation: "rainfed" as typeof IRRIGATIONS[number],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.village || !form.sowing_date || !form.area_ha) {
      setError("Please fill all fields.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const farm = await api.createFarm({
        village: form.village,
        lat: form.location.lat,
        lon: form.location.lon,
        crop: form.crop,
        sowing_date: form.sowing_date,
        area_ha: parseFloat(form.area_ha),
        irrigation: form.irrigation,
        language: lang,
      });
      localStorage.setItem("fk_farm_id", farm.farm_id);
      // Trigger ingest so we have live advisories
      await api.triggerIngest().catch(() => {});
      router.push(`/farm/${farm.farm_id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create farm. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: "100dvh", background: "var(--surface-alt)" }}>
      {/* Header */}
      <div className="top-header">
        <h1 style={{ fontSize: "1.2rem", fontWeight: 700, color: "white" }}>
          🌱 {t("onboarding.title", lang)}
        </h1>
      </div>

      <form onSubmit={handleSubmit} style={{ padding: "24px 16px 40px", maxWidth: "480px", margin: "0 auto" }}>
        {/* Village */}
        <div className="form-group">
          <label className="form-label">{t("onboarding.village", lang)}</label>
          <input
            className="form-input"
            type="text"
            placeholder="e.g. Barhi"
            value={form.village}
            onChange={e => setForm(f => ({ ...f, village: e.target.value }))}
            required
          />
        </div>

        {/* Location (grid cell) */}
        <div className="form-group">
          <label className="form-label">Location (Hazaribagh District)</label>
          <select
            className="form-select"
            value={form.location.name}
            onChange={e => {
              const cell = GRID_CELLS.find(c => c.name === e.target.value);
              if (cell) setForm(f => ({ ...f, location: cell }));
            }}
          >
            {GRID_CELLS.map(cell => (
              <option key={cell.name} value={cell.name}>{cell.name}</option>
            ))}
          </select>
        </div>

        {/* Crop */}
        <div className="form-group">
          <label className="form-label">{t("onboarding.crop", lang)}</label>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
            {CROPS.map(crop => (
              <button
                key={crop}
                type="button"
                onClick={() => setForm(f => ({ ...f, crop }))}
                style={{
                  padding: "12px",
                  border: `2px solid ${form.crop === crop ? "var(--accent)" : "#D4D9D4"}`,
                  borderRadius: "12px",
                  background: form.crop === crop ? "var(--accent-bg)" : "white",
                  color: form.crop === crop ? "var(--accent)" : "var(--text-primary)",
                  fontWeight: 600,
                  cursor: "pointer",
                  minHeight: "48px",
                  transition: "all 0.2s",
                  fontSize: "0.9rem",
                }}
              >
                {t(`crop.${crop}`, lang)}
              </button>
            ))}
          </div>
        </div>

        {/* Sowing date */}
        <div className="form-group">
          <label className="form-label">{t("onboarding.sowing", lang)}</label>
          <input
            className="form-input"
            type="date"
            value={form.sowing_date}
            onChange={e => setForm(f => ({ ...f, sowing_date: e.target.value }))}
            max={new Date().toISOString().split("T")[0]}
            required
          />
        </div>

        {/* Area */}
        <div className="form-group">
          <label className="form-label">{t("onboarding.area", lang)}</label>
          <input
            className="form-input"
            type="number"
            step="0.1"
            min="0.1"
            max="50"
            placeholder="e.g. 1.2"
            value={form.area_ha}
            onChange={e => setForm(f => ({ ...f, area_ha: e.target.value }))}
            required
          />
        </div>

        {/* Irrigation */}
        <div className="form-group">
          <label className="form-label">{t("onboarding.irrigation", lang)}</label>
          <select
            className="form-select"
            value={form.irrigation}
            onChange={e => setForm(f => ({ ...f, irrigation: e.target.value as typeof IRRIGATIONS[number] }))}
          >
            {IRRIGATIONS.map(irr => (
              <option key={irr} value={irr}>{t(`irrigation.${irr}`, lang)}</option>
            ))}
          </select>
        </div>

        {error && (
          <div style={{ color: "var(--severe)", background: "var(--severe-bg)", padding: "12px 16px", borderRadius: "8px", marginBottom: "16px", fontSize: "0.9rem" }}>
            {error}
          </div>
        )}

        <button className="btn-primary" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? <span className="spinner" style={{ width: 20, height: 20 }} /> : t("onboarding.save", lang)}
        </button>
      </form>
    </main>
  );
}
