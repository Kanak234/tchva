"""
Fasal Kavach — Backend API
AI Climate Early-Warning & Crop Advisory for Smallholder Farmers

FastAPI application entry point. Routes are split into routers/.
"""

import json
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

import db  # noqa: E402
from routers import advisories, ask, farms, internal  # noqa: E402

# ---------------------------------------------------------------------------
# Logging — structured JSON, one line per event
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger("fasal_kavach")


# ---------------------------------------------------------------------------
# Lifespan — load baselines and crop calendar once at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load static data files once, share via app.state."""
    # Storage first — everything else assumes it exists.
    # This also initialises the Firebase app that auth.py uses to verify
    # ID tokens, so the two systems share one credential.
    backend = db.init()
    app.state.db_backend = backend
    if backend != "firestore":
        logger.warning(
            json.dumps(
                {
                    "event": "storage_not_persistent",
                    "detail": (
                        "Running on in-memory storage. Data will be lost on "
                        "restart and is not shared between instances. Check "
                        "GOOGLE_APPLICATION_CREDENTIALS and USE_FIRESTORE."
                    ),
                }
            )
        )

    baselines_path = os.path.join(os.path.dirname(__file__), "rules", "baselines.json")
    try:
        with open(baselines_path) as f:
            app.state.baselines = json.load(f)
        logger.info(json.dumps({"event": "baselines_loaded", "path": baselines_path}))
    except FileNotFoundError:
        app.state.baselines = {}
        logger.warning(json.dumps({"event": "baselines_missing", "path": baselines_path}))

    # Load crop calendar
    from rules.crop_calendar import load_crop_calendar

    app.state.crop_calendar = load_crop_calendar()
    logger.info(
        json.dumps(
            {
                "event": "crop_calendar_loaded",
                "crops": list(app.state.crop_calendar.keys()),
            }
        )
    )

    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Fasal Kavach API",
    description=(
        "Climate early-warning and crop-advisory API for smallholder farmers. "
        "Rules decide risk; Gemini communicates it."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js dev server and the deployed frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://fasal-kavach.web.app",
        os.getenv("FRONTEND_ORIGIN", "*"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(farms.router)
app.include_router(advisories.router)
app.include_router(ask.router)
app.include_router(internal.router)


# ---------------------------------------------------------------------------
# Health check — no auth, always up
# ---------------------------------------------------------------------------
@app.get("/healthz", tags=["health"])
async def healthz():
    return {
        "status": "ok",
        "service": "fasal-kavach-api",
        "version": "1.0.0",
        "storage": db.backend_name(),
        "demo_mode": os.getenv("DEMO_MODE", "false").lower() == "true",
    }
