# Data Provenance — Fasal Kavach

Every file in this directory has its source, licence, and transformations documented below.
A civic-tech submission that cannot state where its data came from is a submission with a hole in it.

## Source Catalogue

| File | Source | URL | Downloaded | Licence | Rows | Date Range | Transformations | Known Issues |
|------|--------|-----|------------|---------|------|------------|-----------------|--------------|
| `districts.json` | Team-built | — | 18 Aug 2026 | Internal | 4 grid cells | — | Selected 4 cells at 0.25° resolution covering Hazaribagh district | None |
| `crop_calendar.csv` | ICAR-NRRI Package of Practices + KVK Hazaribagh advisories | Published PDFs | 19 Aug 2026 | Public/Government | 21 stage rows, 4 crops | — | Extracted DAS windows from KVK recommended varieties for Jharkhand; sensitivity values assigned based on published agronomic literature | Assumes transplanted paddy, not direct-seeded; variety-specific windows may vary |
| `seed/demo_farms.json` | Team-built | — | 19 Aug 2026 | Internal | 12 synthetic farms | — | Designed to cover all 4 grid cells, all 4 crops, varied sowing dates and irrigation types | Synthetic but realistic; locations are real villages in Hazaribagh |

## Weather Data Sources (runtime, not stored in this directory)

| Source | What We Take | Access | Notes |
|--------|-------------|--------|-------|
| Open-Meteo | 7-day hourly & daily forecast: temp, rainfall, humidity, wind, soil moisture | Free HTTP API, no key | Primary forecast source. No registration required. |
| Open-Meteo Archive | Daily historical back to 1990 for baseline percentiles | Free HTTP API | Bulk data for the C++ preprocessor |
| IMD (India Met Dept) | District-level warnings and nowcasts | Public pages | Cross-check only; not scraped aggressively |
| data.gov.in | District crop area and season data | Free, API key | Justifies crop choice for the demo district |

## Agronomic Threshold Sources

| Rule | Threshold | Source | Notes |
|------|-----------|--------|-------|
| HEAVY_RAIN_PRE_SPRAY | 40 mm / 48h | ICAR kharif advisory | Foliar sprays and urea wash off above this |
| WATERLOG_RISK | 100 mm / 3 days | ICAR-NRRI drainage guidance | Rainfed and canal-irrigated land |
| HEAT_STRESS_FLOWERING | Paddy 35°C, Wheat 32°C, Tomato 34°C, Maize 38°C | ICAR-NRRI spikelet sterility research | During anthesis/flowering |
| DRY_SPELL | 7 consecutive days < 2.5 mm | TEAM ESTIMATE | Calibrated against IMD dry-spell definitions |
| PEST_WEATHER_WINDOW | Humidity >85%, t_min in crop-specific band, 3+ days | ICAR IPM guidelines | Crop-specific pest bands |
| HARVEST_RAIN_CLASH | 25 mm within harvest window | TEAM ESTIMATE | Needs field validation |
| FROST_RISK | t_min < 4°C | IMD cold wave criteria for Jharkhand | Rabi crops and vegetables only |
