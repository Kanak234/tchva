# Fasal Kavach 🌾

**AI Climate Early-Warning & Crop Advisory for Smallholder Farmers**

> Build with AI: Code for Communities (2nd Edition)  
> Team: Kanak Prabhakar (Lead) — Hazaribagh, Jharkhand

---

## What it does

Fasal Kavach watches the weather against the crop a farmer is actually growing.
When a risk crosses a threshold, it sends that farmer a specific, **spoken instruction
in their own language** — not a generic forecast.

**The core design principle:** Deterministic agronomic rules decide whether there is
a risk. Gemini only phrases it. The AI cannot invent a warning.

---

## Three modes

Fasal Kavach operates in one of three modes depending on your configuration:

* **Cloud Mode (Gemini via Render / Cloud Run)**:
  - **Data**: Real-time live weather data from Open-Meteo, evaluated against deterministic agronomic rules.
  - **AI Backend**: Google Gemini 2.5 Flash via google-genai SDK.
  - **Storage**: In-memory (on Render) or persistent (with Firestore).
* **Local Mode (Ollama on Laptop)**:
  - **Data**: Real-time live weather data, evaluated against deterministic agronomic rules.
  - **AI Backend**: Local Ollama server (`USE_OLLAMA=true`) running Gemma2 or another local LLM for offline AI execution.
  - **Storage**: In-memory or Firestore.
* **Demo Mode (In-browser Mock)**:
  - **Data**: **Simulated static data** returned by the client fallback.
  - **AI Backend**: None (mocked local advisories).
  - **UI Indicator**: Explicitly labeled at the top of every screen with an amber warning banner: *Demo data — backend not connected*.

---

## Quick start (under 10 minutes)

```bash
git clone https://github.com/Kanak234/fasal-kavach.git
cd fasal-kavach
cp .env.example .env          # backend
cp .env.example web/.env.local # frontend
# Paste your keys into both
```

**First time?** Read [`FIREBASE_SETUP.md`](FIREBASE_SETUP.md) first —
fifteen minutes in the Firebase console, no code. Without it the app runs
on in-memory storage and forgets everything on restart.

You can skip Firebase entirely and still run the rules engine:

```bash
USE_FIRESTORE=false DEMO_MODE=true uvicorn main:app --reload --port 8080
```

### Backend
```bash
cd api
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
# → http://localhost:8080/docs
```

### Frontend (separate terminal)
```bash
cd web
npm install
npm run dev
# → http://localhost:3000
```

### Run tests
```bash
cd api && pytest -q      # 88 tests
```

### Check storage is real — do this before every demo
```bash
curl http://localhost:8080/internal/status
# {"backend": "firestore", "persistent": true, "farms_stored": 12}
```

If it reports `"backend": "memory"`, Firestore did not connect and your
data will disappear on restart. The startup log prints the reason.

### Seed the demo farms
```bash
curl -X POST http://localhost:8080/internal/seed
```

Twelve synthetic farms from `data/seed/demo_farms.json`. The farms are
invented; the weather they are evaluated against is fetched live from
Open-Meteo and is not.

### Trigger ingest (generate advisories)
```bash
curl -X POST http://localhost:8080/internal/ingest
```

Watch `template_fallbacks` in the response. If it is high, `GEMINI_API_KEY`
is missing or rate limited — the app still works, which is the point of
the fallback ladder, but know which path your demo is on.

### Lint
```bash
ruff check .
python3 scripts/check_locale_keys.py
```

---

## How farmer data is protected

A judge will ask this. The short answer:

1. Farmers sign in with **Google Sign-In** (Firebase Auth).
2. Every API call carries a **signed ID token**, verified server-side in
   `api/auth.py` against Google's public keys. It cannot be forged.
3. Every farm-scoped read checks **ownership**. One farmer cannot read
   another's advisories — `test_api_flow.py` proves it.
4. `firestore.rules` enforces the same thing for any direct browser
   access to the database.
5. Data lives in **Firestore, asia-south1 (Mumbai)** — on Indian
   infrastructure.
6. The district summary endpoint returns **counts only**. No farm ids, no
   names, nothing identifying an individual.

`DEMO_MODE=true` accepts unauthenticated calls as `demo_user` so a live
audience can tap through without waiting for Google sign-in. It is a labelled
environment flag, not a hidden bypass. Set it to `false` for anything with
real farmers in it.

---

## Architecture

```
                       ┌─── (Backend Connected) ───► FastAPI (Render / Cloud Run)
                       │                              ├─── AI: Gemini API (Cloud)
                       │                              ├─── AI: Local Ollama (Laptop)
                       │                              └─── Database: Firestore / In-memory
Next.js PWA ───────────┤
                       │
                       └─── (Backend Offline) ─────► In-browser Mock Fallback (Demo Mode)
                                                      └─── Warning Banner Active
```

**Rules decide. AI communicates.**

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 14, TailwindCSS, Firebase Auth |
| Backend | FastAPI (Python 3.11), Cloud Run |
| Database | Cloud Firestore |
| AI | Gemini 2.5 Flash OR Local Ollama (Gemma2, Gemma:2b, etc.) |
| Scheduling | Cloud Scheduler |
| Preprocessing | C++20 CLI tool (offline, not in request path) |

---

## Demo path (Section 5.1)

1. Open the public URL (Note: If the backend is not yet deployed or is offline, the app will show a prominent amber warning banner indicating simulated demo mode).
2. Log in (or use Demo Farm shortcut)  
3. Create a farm: crop = paddy, sowing = 15 July, area = 1.2 ha
4. See a live alert generated from real forecast data
5. Tap the speaker and hear it read aloud in Hindi
6. Tap "Kya hua?" and see the exact rainfall/temperature numbers
7. **Change the crop to maize** — the advisory changes accordingly (this is the key step)

---

## Demo district

**Hazaribagh, Jharkhand** — 4 grid cells at 0.25° resolution,
4 crops (paddy, maize, wheat, tomato), Hindi and English at Tier 1.

---

## Environment variables

Copy `.env.example` to `.env` and fill in:

```
GEMINI_API_KEY=...
USE_OLLAMA=false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2
GOOGLE_CLOUD_PROJECT=fasal-kavach
INTERNAL_TOKEN=...
NEXT_PUBLIC_API_BASE=http://localhost:8080
NEXT_PUBLIC_FIREBASE_*=...  (from Firebase console)
```

**Never commit `.env` or any key file.**

*Note: During production deployment, replace `NEXT_PUBLIC_API_BASE=RENDER_URL_HERE` in `web/.env.production` with your actual Render backend URL before running `npm run build` and `firebase deploy`.*

---

## Repository structure

```
fasal-kavach/
├── api/                 # FastAPI backend (Kanak)
│   ├── main.py
│   ├── routers/         # farms, advisories, ask, internal
│   ├── rules/           # engine, definitions, templates, crop_calendar
│   ├── ai/              # Gemini client, cache
│   ├── ingest/          # Open-Meteo fetch, job runner
│   ├── models/          # Pydantic canonical models
│   └── tests/           # pytest, 100% rule coverage
├── web/                 # Next.js PWA (Member 2)
│   └── src/
│       ├── app/         # 6 screens
│       └── lib/         # api.ts, tts.ts, i18n.ts, firebase.ts
├── tools/preprocess/    # C++20 offline baseline tool
├── data/                # crop_calendar.csv, districts.json
├── Dockerfile
├── firestore.rules
└── .github/workflows/ci.yml
```

---

## Testing

```bash
cd api && pytest -q --tb=short
# Expected: all rules pass, calendar edge cases pass, AI validation pass
```

---

## Deployment

See `docs/BUILD_SPEC.docx` Section 29 for the full runbook.

```bash
# Backend → Cloud Run
gcloud run deploy fasal-kavach-api --source api/ --region asia-south1

# Frontend → Firebase Hosting
cd web && npm run build && firebase deploy --only hosting
```

---

## Data provenance

See `data/README.md` for source, licence, and transformation notes for every data file.

---

## Honest claims

- Working end-to-end prototype for **one district, four crops**
- **Seeded with real weather data** from Open-Meteo (when backend is connected)
- Rules engine is **fully unit-tested** with boundary conditions
- Gemini output is **validated** — number containment check, no pesticide names
- **Graceful degradation**: template fallbacks when AI is unavailable, and automatic transparent transition to in-browser demo/mock fallback with a visible UI warning banner when the backend is disconnected
- **Transparency**: In-browser demo mode uses simulated data and does not run the backend rules engine, which is honestly declared to the user via the top warning banner.
- Not claiming: nationwide scale, field-validated agronomy, ML model training

---

*Section numbers in this repo refer to BUILD_SPEC.docx — the single source of truth.*
