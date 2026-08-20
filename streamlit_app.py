"""
Fasal Kavach — Streamlit Demo Dashboard
========================================
Deployable to share.streamlit.io in one click.

This app demonstrates the deterministic rules engine end-to-end:
  1. Pick a crop, sowing date, and irrigation type
  2. Adjust a synthetic 7-day forecast (sliders)
  3. Watch the rules engine fire or stay silent in real-time
  4. See the exact evidence that triggered each alert
  5. Read the template advisory in Hindi or English

The Gemini layer is optional — the rules engine runs with zero API keys.
"""

import os
import sys
from datetime import date, timedelta

# Add the api/ directory to the Python path so we can use the engine directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

import streamlit as st

# Page config — must be first Streamlit call
st.set_page_config(
    page_title="Fasal Kavach — Live Demo",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Imports after path setup
# ---------------------------------------------------------------------------
from models import Farm, WeatherDay
from rules.crop_calendar import load_crop_calendar, stage_for
from rules.engine import evaluate
from rules.templates import get_template

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  /* Header */
  .main-header {
    background: linear-gradient(135deg, #17563B 0%, #1E6B4A 100%);
    padding: 24px 32px;
    border-radius: 16px;
    margin-bottom: 24px;
    color: white;
  }
  .main-header h1 { color: white; margin: 0; font-size: 2rem; }
  .main-header p { color: rgba(255,255,255,0.8); margin: 4px 0 0; }

  /* Alert cards */
  .alert-severe {
    background: #FFF0EE;
    border-left: 5px solid #B3261E;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
  }
  .alert-moderate {
    background: #FFF8EC;
    border-left: 5px solid #B26A00;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
  }
  .alert-low {
    background: #E8F5ED;
    border-left: 5px solid #17563B;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
  }
  .alert-title { font-weight: 700; font-size: 1.05rem; margin-bottom: 4px; }
  .evidence-box {
    background: #F7F9F7;
    border: 1px solid #D4DDD4;
    border-radius: 8px;
    padding: 12px 16px;
    font-family: monospace;
    font-size: 0.85rem;
  }
  .safe-banner {
    background: #E8F5ED;
    border: 2px solid #17563B;
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    margin: 16px 0;
  }
  /* Metric cards */
  div[data-testid="metric-container"] {
    background: white;
    border-radius: 12px;
    padding: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load static data
# ---------------------------------------------------------------------------
@st.cache_resource
def load_data():
    import json
    baselines_path = os.path.join(os.path.dirname(__file__), "api", "rules", "baselines.json")
    try:
        with open(baselines_path) as f:
            baselines = json.load(f)
    except FileNotFoundError:
        baselines = {}
    crop_calendar = load_crop_calendar()
    return baselines, crop_calendar

baselines, crop_calendar = load_data()

# ---------------------------------------------------------------------------
# Sidebar — Farm configuration
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🌾 Farm Setup")

    st.markdown("**Crop**")
    crop = st.selectbox(
        "crop",
        ["paddy", "maize", "wheat", "tomato"],
        format_func={"paddy": "🌾 Paddy (Rice)", "maize": "🌽 Maize", "wheat": "🌱 Wheat", "tomato": "🍅 Tomato"}.get,
        label_visibility="collapsed",
    )

    st.markdown("**Sowing Date**")
    default_sowing = date.today() - timedelta(days=45)
    sowing_date = st.date_input("sowing_date", value=default_sowing, label_visibility="collapsed")

    st.markdown("**Irrigation**")
    irrigation = st.selectbox(
        "irrigation",
        ["rainfed", "canal", "borewell", "mixed"],
        format_func={"rainfed": "☁️ Rainfed", "canal": "🏞️ Canal", "borewell": "🔩 Borewell", "mixed": "⚡ Mixed"}.get,
        label_visibility="collapsed",
    )

    st.markdown("**Area (hectares)**")
    area_ha = st.slider("area_ha", 0.1, 5.0, 1.2, 0.1, label_visibility="collapsed")

    st.markdown("**Language**")
    lang = st.radio("Language", ["hi", "en"], format_func={"hi": "हिंदी", "en": "English"}.get, horizontal=True)

    st.divider()
    st.markdown("**Grid Cell**")
    grid_id = st.selectbox(
        "grid",
        ["HZB-01", "HZB-02", "HZB-03", "HZB-04"],
        format_func={
            "HZB-01": "Barhi / NW",
            "HZB-02": "Daru / NE",
            "HZB-03": "Keredari / SW",
            "HZB-04": "Ichak / SE",
        }.get,
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("### 📡 7-Day Forecast Simulator")
    st.caption("Adjust to simulate different weather scenarios")

    rain_pattern = st.selectbox(
        "Weather Scenario",
        ["Normal", "Heavy Rain", "Dry Spell", "Heat Wave", "Pest Weather", "Harvest Rain"],
    )

    # Preset scenarios
    SCENARIOS = {
        "Normal":       {"rain": [5,  2,  0,  3,  8,  1,  0],  "tmax": [31]*7, "tmin": [22]*7, "hum": [68]*7},
        "Heavy Rain":   {"rain": [42, 35, 28, 5,  2,  0,  0],  "tmax": [29]*7, "tmin": [23]*7, "hum": [88]*7},
        "Dry Spell":    {"rain": [0,  1,  0,  0,  0,  0,  0],  "tmax": [36]*7, "tmin": [24]*7, "hum": [45]*7},
        "Heat Wave":    {"rain": [0,  0,  0,  2,  0,  1,  0],  "tmax": [38, 39, 37, 36, 38, 40, 37], "tmin": [26]*7, "hum": [55]*7},
        "Pest Weather": {"rain": [8,  5,  12, 3,  2,  6,  4],  "tmax": [32]*7, "tmin": [24, 25, 23, 24, 25, 23, 24], "hum": [90, 88, 92, 87, 91, 86, 89]},
        "Harvest Rain": {"rain": [28, 15, 5,  0,  2,  0,  1],  "tmax": [30]*7, "tmin": [21]*7, "hum": [75]*7},
    }
    preset = SCENARIOS[rain_pattern]

    # Start with preset values; expander allows fine-tuning
    rain_vals = [float(v) for v in preset["rain"]]
    tmax_vals = [float(v) for v in preset["tmax"]]
    tmin_vals = [float(v) for v in preset["tmin"]]
    hum_vals  = [float(v) for v in preset["hum"]]

    with st.expander("Fine-tune forecast"):
        rain_vals = [st.slider(f"Day {i+1} Rain (mm)", 0.0, 150.0, float(preset["rain"][i]), 0.5, key=f"rain_{i}") for i in range(7)]
        tmax_vals = [st.slider(f"Day {i+1} Tmax (°C)", 20.0, 50.0, float(preset["tmax"][i]), 0.5, key=f"tmax_{i}") for i in range(7)]
        tmin_vals = [st.slider(f"Day {i+1} Tmin (°C)", 5.0, 35.0, float(preset["tmin"][i]), 0.5, key=f"tmin_{i}") for i in range(7)]
        hum_vals  = [st.slider(f"Day {i+1} Humidity (%)", 20.0, 100.0, float(preset["hum"][i]), 1.0, key=f"hum_{i}") for i in range(7)]

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

# Header
st.markdown("""
<div class="main-header">
  <h1>🌾 Fasal Kavach</h1>
  <p>AI Climate Early-Warning & Crop Advisory · Demo Dashboard · Hazaribagh, Jharkhand</p>
</div>
""", unsafe_allow_html=True)

# Build objects
today = date.today()

farm = Farm(
    farm_id="demo_farm",
    owner_uid="demo",
    village="Barhi",
    grid_id=grid_id,
    lat=24.0,
    lon=85.25,
    crop=crop,
    sowing_date=sowing_date,
    area_ha=area_ha,
    irrigation=irrigation,
    language=lang,
)

stage = stage_for(crop, sowing_date, today, crop_calendar)

forecast = [
    WeatherDay(
        grid_id=grid_id,
        date=today + timedelta(days=i),
        t_max_c=tmax_vals[i],
        t_min_c=tmin_vals[i],
        rain_mm=rain_vals[i],
        rain_prob=min(1.0, rain_vals[i] / 50),
        humidity_pct=hum_vals[i],
        wind_kph_max=12.0,
        source="demo",
    )
    for i in range(7)
]

# Run the rules engine
events = evaluate(farm, forecast, stage, baselines, today)

# ---------------------------------------------------------------------------
# Summary metrics row
# ---------------------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("📅 Days After Sowing", stage.das_current)
with c2:
    crop_labels = {"paddy": "Paddy", "maize": "Maize", "wheat": "Wheat", "tomato": "Tomato"}
    st.metric("🌾 Crop & Stage", crop_labels[crop], stage.name.replace("_", " ").title())
with c3:
    severe_count = sum(1 for e in events if e.severity == "SEVERE")
    st.metric("🚨 Urgent Alerts", severe_count, delta=None)
with c4:
    st.metric("⚡ Alerts Total", len(events))
with c5:
    total_rain = sum(rain_vals)
    st.metric("🌧 7-Day Rain", f"{total_rain:.0f} mm")

st.divider()

# ---------------------------------------------------------------------------
# Two-column layout: alerts + forecast
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([3, 2])

with col_left:
    st.markdown("### 🔔 Advisories")

    if not events:
        st.markdown("""
        <div class="safe-banner">
          <h2>✅</h2>
          <h3>No alerts for this scenario</h3>
          <p>The rules engine found no conditions that exceed thresholds for your crop and stage.<br>
          Try switching to "Heavy Rain" or "Heat Wave" in the sidebar.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Sort: SEVERE first
        sev_order = {"SEVERE": 0, "MODERATE": 1, "LOW": 2}
        for event in sorted(events, key=lambda e: sev_order[e.severity]):
            sev_class = event.severity.lower()
            sev_icon = {"SEVERE": "⚠️", "MODERATE": "⚡", "LOW": "ℹ️"}[event.severity]
            sev_label = {"SEVERE": "अत्यावश्यक / Urgent", "MODERATE": "सावधान / Caution", "LOW": "सूचना / Note"}[event.severity]

            # Get template advisory
            template = get_template(event.rule_id, lang, event.evidence, crop=crop, stage_window=stage.name)

            with st.expander(f"{sev_icon} [{sev_label}] {template['headline'] if template else event.rule_id}", expanded=(event.severity == "SEVERE")):
                if template:
                    st.markdown(f"**{template['headline']}**")
                    st.markdown(template["body"])

                    st.markdown("**Actions:**")
                    for i, action in enumerate(template["actions"], 1):
                        st.markdown(f"{i}. {action}")

                    st.markdown("---")
                    st.markdown(f"🔊 **Listen:** *{template['spoken_script']}*")

                st.markdown("**🔍 Evidence (why this alert fired):**")
                evidence_lines = []
                for k, v in event.evidence.items():
                    if k == "observed_at":
                        continue
                    label = k.replace("_", " ").title()
                    if isinstance(v, float):
                        evidence_lines.append(f"  {label}: {v:.1f}")
                    else:
                        evidence_lines.append(f"  {label}: {v}")
                st.code("\n".join(evidence_lines), language="yaml")

                st.caption(f"📖 Source: {event.source_note}")
                st.caption(f"🆔 Rule: `{event.rule_id}` · Event: `{event.event_id}`")

with col_right:
    st.markdown("### 📡 7-Day Forecast")
    import pandas as pd
    forecast_df = pd.DataFrame([
        {
            "Date": (today + timedelta(days=i)).strftime("%a %d/%m"),
            "Rain (mm)": rain_vals[i],
            "Max °C": tmax_vals[i],
            "Min °C": tmin_vals[i],
            "Humidity %": hum_vals[i],
        }
        for i in range(7)
    ])
    st.dataframe(
        forecast_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Rain (mm)": st.column_config.ProgressColumn("Rain (mm)", min_value=0, max_value=150, format="%.1f mm"),
            "Max °C": st.column_config.NumberColumn("Max °C", format="%.1f °C"),
        }
    )

    st.markdown("### 🌱 Growth Stage")
    stage_data = {
        "Stage": stage.name.replace("_", " ").title(),
        "DAS Current": stage.das_current,
        "DAS Range": f"{stage.das_start}–{stage.das_end}",
        "Water Sensitivity": stage.sensitive_water.upper(),
        "Heat Sensitivity": stage.sensitive_heat.upper(),
        "Pest Sensitivity": stage.sensitive_pest.upper(),
        "Input Window": "✅ Yes" if stage.input_window else "❌ No",
    }
    for k, v in stage_data.items():
        col_a, col_b = st.columns([2, 1])
        col_a.markdown(f"**{k}**")
        col_b.markdown(str(v))

    st.markdown("### 📊 Rule Thresholds")
    threshold_df = pd.DataFrame([
        {"Rule": "Heavy Rain Pre-Spray", "Threshold": "40 mm / 48h", "Source": "ICAR Kharif"},
        {"Rule": "Waterlog Risk",        "Threshold": "100 mm / 3 days", "Source": "ICAR-NRRI"},
        {"Rule": "Heat Stress (Paddy)",  "Threshold": "35°C / 2+ days", "Source": "ICAR-NRRI"},
        {"Rule": "Heat Stress (Wheat)",  "Threshold": "32°C / 2+ days", "Source": "ICAR-NRRI"},
        {"Rule": "Dry Spell",            "Threshold": "7 days <2.5mm", "Source": "IMD"},
        {"Rule": "Pest Window",          "Threshold": "Humidity >85% / 3d", "Source": "ICAR IPM"},
        {"Rule": "Harvest Rain",         "Threshold": "25 mm at harvest", "Source": "Team"},
        {"Rule": "Frost Risk",           "Threshold": "Tmin <4°C", "Source": "IMD Jharkhand"},
    ])
    st.dataframe(threshold_df, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# Demo path section
# ---------------------------------------------------------------------------
st.divider()
st.markdown("### 🎯 Demo Path — Try This")
d1, d2, d3, d4 = st.columns(4)
with d1:
    st.info("**Step 1**\nSet crop = Paddy, sowing = 15 Jul, rainfed")
with d2:
    st.info("**Step 2**\nSelect 'Heavy Rain' scenario → see waterlog alert")
with d3:
    st.info("**Step 3**\nChange crop to Maize → alert changes accordingly")
with d4:
    st.info("**Step 4**\nTry 'Heat Wave' at flowering → heat stress alert")

# ---------------------------------------------------------------------------
# About section
# ---------------------------------------------------------------------------
with st.expander("ℹ️ About this demo"):
    st.markdown("""
    **Fasal Kavach** is an AI Climate Early-Warning & Crop Advisory system for smallholder farmers.

    **How it works:**
    - **Rules Engine** (Python, deterministic) decides whether there is a risk — pure function, fully unit-tested
    - **Gemini 2.5 Flash** only phrases the advisory in the farmer's language
    - **AI cannot invent a warning** — it is constrained by JSON schema and number containment checks

    **This demo runs the rules engine directly** — no API keys needed.
    Add a `GEMINI_API_KEY` to get AI-generated advisories in Hindi, Khortha, Bengali, or English.

    **Stack:** FastAPI · Next.js PWA · Cloud Firestore · Cloud Run · Open-Meteo
    **Location:** Hazaribagh, Jharkhand, India

    **Build with AI: Code for Communities (2nd Edition)**
    """)
    st.caption("Source: [github.com/Kanak234/fasal-kavach](https://github.com/Kanak234/fasal-kavach)")
