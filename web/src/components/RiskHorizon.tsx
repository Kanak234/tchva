"use client";
/**
 * Risk Horizon — the one thing this app is for.
 *
 * Seven columns, one per day, left to right from today. Column height and
 * colour carry the risk; the mono readouts underneath carry the numbers
 * that produced it. A farmer should be able to answer "is my field in
 * trouble this week?" without reading a single sentence.
 *
 * The thresholds below are lifted from api/rules/definitions.py so the
 * strip and the advisories agree. If a threshold moves there, move it
 * here too — a strip that disagrees with the alerts underneath it is
 * worse than no strip.
 */
import { type Lang } from "@/lib/i18n";

/** api/rules/definitions.py — HEAT_THRESHOLDS_C */
const HEAT_C: Record<string, number> = {
  paddy: 35,
  wheat: 32,
  tomato: 34,
  maize: 38,
};

/** api/rules/definitions.py — HEAVY_RAIN_THRESHOLD_MM */
const HEAVY_RAIN_MM = 40;
/** api/rules/definitions.py — DRY_SPELL_RAIN_LIMIT_MM */
const DRY_MM = 2.5;

export type Risk = "none" | "low" | "moderate" | "severe";

export interface HorizonDay {
  date: string;
  t_max_c: number;
  t_min_c: number;
  rain_mm: number;
  humidity_pct?: number;
}

/**
 * Score one day against the crop's own thresholds.
 *
 * Deliberately conservative: this is a glanceable summary, not a second
 * rules engine. Anything it flags as severe should already have an
 * advisory attached; the strip only makes the shape of the week visible.
 */
export function scoreDay(day: HorizonDay, crop: string): Risk {
  const heat = HEAT_C[crop] ?? 35;
  let level: Risk = "none";

  const bump = (r: Risk) => {
    const order: Risk[] = ["none", "low", "moderate", "severe"];
    if (order.indexOf(r) > order.indexOf(level)) level = r;
  };

  // Heat
  if (day.t_max_c >= heat + 4) bump("severe");
  else if (day.t_max_c >= heat + 1.5) bump("moderate");
  else if (day.t_max_c >= heat) bump("low");

  // Rain
  if (day.rain_mm >= HEAVY_RAIN_MM) bump("severe");
  else if (day.rain_mm >= HEAVY_RAIN_MM * 0.55) bump("moderate");
  else if (day.rain_mm >= HEAVY_RAIN_MM * 0.25) bump("low");

  // Humid + warm night — the pest window.
  // Only ever "low". Through a Jharkhand monsoon this is true almost every
  // day, so letting it reach "moderate" paints the whole strip amber and
  // the farmer learns to ignore it.
  if ((day.humidity_pct ?? 0) >= 85 && day.t_min_c >= 20) bump("low");

  return level;
}

const FILL: Record<Risk, number> = { none: 16, low: 40, moderate: 68, severe: 100 };

const LOCALE: Record<Lang, string> = {
  hi: "hi-IN",
  kho: "hi-IN",
  bn: "bn-IN",
  en: "en-IN",
};

const LABEL: Record<Lang, { title: string; sub: string; calm: string; watch: string; act: string }> = {
  hi: { title: "सात दिन का खतरा", sub: "आज से", calm: "ठीक", watch: "सावधान", act: "तुरंत" },
  kho: { title: "सात दिन के खतरा", sub: "आज सें", calm: "ठीक", watch: "सावधान", act: "तुरंत" },
  bn: { title: "সাত দিনের ঝুঁকি", sub: "আজ থেকে", calm: "ঠিক", watch: "সতর্ক", act: "এখনই" },
  en: { title: "Seven-day risk", sub: "from today", calm: "Calm", watch: "Watch", act: "Act now" },
};

export default function RiskHorizon({
  forecast,
  crop,
  lang,
}: {
  forecast: HorizonDay[];
  crop: string;
  lang: Lang;
}) {
  const days = forecast.slice(0, 7);
  if (days.length === 0) return null;

  const locale = LOCALE[lang] ?? "hi-IN";
  const copy = LABEL[lang] ?? LABEL.hi;
  const peak = days.reduce<Risk>((worst, d) => {
    const r = scoreDay(d, crop);
    const order: Risk[] = ["none", "low", "moderate", "severe"];
    return order.indexOf(r) > order.indexOf(worst) ? r : worst;
  }, "none");

  const verdict =
    peak === "severe" ? copy.act : peak === "moderate" ? copy.watch : copy.calm;
  const verdictColor =
    peak === "severe"
      ? "var(--laterite)"
      : peak === "moderate"
        ? "var(--turmeric)"
        : "var(--paddy)";

  return (
    <section className="horizon rise" aria-label={copy.title}>
      <div className="horizon__head">
        <div>
          <h2 className="eyebrow" style={{ color: "var(--ink-2)" }}>
            {copy.title}
          </h2>
          <p className="data" style={{ fontSize: "0.63rem", color: "var(--ink-3)", marginTop: 2 }}>
            {copy.sub}
          </p>
        </div>
        <span
          className="tag"
          style={{
            color: verdictColor,
            borderColor: verdictColor,
            background: "transparent",
          }}
        >
          {verdict}
        </span>
      </div>

      <div
        className="horizon__grid"
        style={{ gridTemplateColumns: `repeat(${days.length}, 1fr)` }}
      >
        {days.map((day, i) => {
          const risk = scoreDay(day, crop);
          const d = new Date(day.date);
          const dry = day.rain_mm < DRY_MM;
          return (
            <div key={day.date} className={`hcol${i === 0 ? " hcol--today" : ""}`}>
              <div
                className="hcol__well"
                title={`${d.toLocaleDateString(locale, { day: "numeric", month: "short" })} — ${Math.round(day.t_max_c)}°C, ${day.rain_mm.toFixed(1)} mm`}
              >
                <div
                  className={`hcol__fill hcol__fill--${risk}`}
                  style={{
                    height: `${FILL[risk]}%`,
                    animationDelay: `${i * 55}ms`,
                  }}
                />
              </div>
              <span className={`hcol__day${i === 0 ? " hcol__day--today" : ""}`}>
                {d.toLocaleDateString(locale, { weekday: "narrow" })}
              </span>
              <span className="hcol__temp">{Math.round(day.t_max_c)}°</span>
              <span className={`hcol__rain${dry ? " hcol__rain--dry" : ""}`}>
                {dry ? "—" : day.rain_mm.toFixed(0)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="horizon__legend">
        <span className="legend-item">
          <i className="legend-swatch" style={{ background: "var(--paddy)" }} />
          {copy.calm}
        </span>
        <span className="legend-item">
          <i className="legend-swatch" style={{ background: "var(--turmeric)" }} />
          {copy.watch}
        </span>
        <span className="legend-item">
          <i className="legend-swatch" style={{ background: "var(--laterite)" }} />
          {copy.act}
        </span>
        <span className="legend-item" style={{ marginLeft: "auto", color: "var(--ink-3)" }}>
          °C · MM
        </span>
      </div>
    </section>
  );
}
