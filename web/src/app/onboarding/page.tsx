"use client";
/**
 * Onboarding — describe the field once, get warnings for the season.
 *
 * Every field here feeds the rules engine: the grid cell picks the
 * weather series, the crop picks the temperature thresholds, and the
 * sowing date drives days-after-sowing and growth stage.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { t, type Lang } from "@/lib/i18n";
import { IconCrop } from "@/components/Icons";

const CROPS = ["paddy", "maize", "wheat", "tomato"] as const;
const IRRIGATIONS = ["rainfed", "canal", "borewell", "mixed"] as const;

/** Hazaribagh district grid-cell centres — the resolution of the forecast. */
const GRID_CELLS = [
  { name: "Barhi / Hazaribagh NW", lat: 24.0, lon: 85.25 },
  { name: "Daru / Hazaribagh NE", lat: 24.0, lon: 85.5 },
  { name: "Keredari / Hazaribagh SW", lat: 23.75, lon: 85.25 },
  { name: "Ichak / Hazaribagh SE", lat: 23.75, lon: 85.5 },
];

export default function OnboardingPage() {
  const router = useRouter();
  const lang =
    ((typeof window !== "undefined" ? localStorage.getItem("fk_lang") : "hi") as Lang) ||
    "hi";

  const [form, setForm] = useState({
    village: "",
    location: GRID_CELLS[0],
    crop: "paddy" as (typeof CROPS)[number],
    sowing_date: "",
    area_ha: "",
    irrigation: "rainfed" as (typeof IRRIGATIONS)[number],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.village || !form.sowing_date || !form.area_ha) {
      setError("Fill in the village, sowing date and area to continue.");
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
      // Pull a fresh forecast so the first screen has something on it.
      await api.triggerIngest().catch(() => {});
      router.push(`/farm/${farm.farm_id}`);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "The farm could not be saved. Check your connection and try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="masthead">
        <div className="masthead__wrap">
          <h1 className="masthead__title">{t("onboarding.title", lang)}</h1>
          <span className="masthead__rule" />
        </div>
      </header>

      <form onSubmit={handleSubmit} className="sheet" style={{ paddingBottom: "var(--sp-6)" }}>
        <div className="section-head">
          <span className="eyebrow">Your field</span>
          <span className="data" style={{ fontSize: "0.65rem", color: "var(--ink-3)" }}>
            3 / 3
          </span>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="village">
            {t("onboarding.village", lang)}
          </label>
          <input
            id="village"
            className="input"
            type="text"
            placeholder="Barhi"
            value={form.village}
            onChange={(e) => setForm((f) => ({ ...f, village: e.target.value }))}
            required
          />
        </div>

        <div className="field">
          <label className="field__label" htmlFor="cell">
            Grid cell · Hazaribagh
          </label>
          <select
            id="cell"
            className="select"
            value={form.location.name}
            onChange={(e) => {
              const cell = GRID_CELLS.find((c) => c.name === e.target.value);
              if (cell) setForm((f) => ({ ...f, location: cell }));
            }}
          >
            {GRID_CELLS.map((cell) => (
              <option key={cell.name} value={cell.name}>
                {cell.name}
              </option>
            ))}
          </select>
          <p
            className="data"
            style={{ fontSize: "0.63rem", color: "var(--ink-3)", marginTop: 5 }}
          >
            {form.location.lat.toFixed(2)}°N · {form.location.lon.toFixed(2)}°E
          </p>
        </div>

        <div className="field">
          <span className="field__label">{t("onboarding.crop", lang)}</span>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {CROPS.map((crop) => {
              const on = form.crop === crop;
              return (
                <button
                  key={crop}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, crop }))}
                  aria-pressed={on}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    minHeight: 52,
                    padding: "12px",
                    border: `1.5px solid ${on ? "var(--paddy)" : "var(--rule)"}`,
                    borderRadius: "var(--r-btn)",
                    background: on ? "var(--paddy-wash)" : "var(--card)",
                    color: on ? "var(--paddy-deep)" : "var(--ink-2)",
                    fontFamily: "var(--face-body)",
                    fontWeight: 600,
                    fontSize: "0.88rem",
                    cursor: "pointer",
                    transition: "all 0.16s ease",
                  }}
                >
                  <IconCrop size={17} />
                  {t(`crop.${crop}`, lang)}
                </button>
              );
            })}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--sp-3)" }}>
          <div className="field">
            <label className="field__label" htmlFor="sowing">
              {t("onboarding.sowing", lang)}
            </label>
            <input
              id="sowing"
              className="input"
              type="date"
              value={form.sowing_date}
              onChange={(e) => setForm((f) => ({ ...f, sowing_date: e.target.value }))}
              max={new Date().toISOString().split("T")[0]}
              required
            />
          </div>

          <div className="field">
            <label className="field__label" htmlFor="area">
              {t("onboarding.area", lang)}
            </label>
            <input
              id="area"
              className="input"
              type="number"
              step="0.1"
              min="0.1"
              max="50"
              placeholder="1.2"
              value={form.area_ha}
              onChange={(e) => setForm((f) => ({ ...f, area_ha: e.target.value }))}
              required
            />
          </div>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="irrigation">
            {t("onboarding.irrigation", lang)}
          </label>
          <select
            id="irrigation"
            className="select"
            value={form.irrigation}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                irrigation: e.target.value as (typeof IRRIGATIONS)[number],
              }))
            }
          >
            {IRRIGATIONS.map((irr) => (
              <option key={irr} value={irr}>
                {t(`irrigation.${irr}`, lang)}
              </option>
            ))}
          </select>
        </div>

        {error && (
          <div role="alert" className="notice notice--error" style={{ marginBottom: "var(--sp-4)" }}>
            {error}
          </div>
        )}

        <button className="btn btn--solid btn--block" type="submit" disabled={loading}>
          {loading ? (
            <span className="spinner spinner--light" style={{ width: 18, height: 18 }} />
          ) : (
            t("onboarding.save", lang)
          )}
        </button>
      </form>
    </main>
  );
}
