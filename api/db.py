"""
db.py — The ONLY file in the backend that talks to storage.
Section 14 (Firestore schema) made real.

WHY THIS FILE EXISTS
--------------------
Before this file, farms and advisories lived in module-level Python dicts.
That works on your laptop and breaks in two ways on Cloud Run:

  1. Cloud Run scales to zero when nobody uses the service. The container
     dies, and every dict dies with it. A judge who creates a farm, waits
     ten minutes, and reloads the page gets a 404.
  2. Cloud Run runs several containers under load. Container A holds the
     farm; container B answers the next request and has never seen it.

Firestore writes to disk on Google's servers, so neither happens.

TWO BACKENDS, ONE INTERFACE
---------------------------
  FirestoreBackend — real Firestore, used when credentials are present.
  MemoryBackend    — dicts, used in tests and when no credentials exist.

Routers never know which one is running. That is the point: you can run
`pytest` with no Firebase project, and the same code path runs in
production against real Firestore.

BLOCKING CALLS
--------------
firebase-admin is a synchronous library. Calling it directly inside an
`async def` route would block FastAPI's event loop and stall every other
request. So every Firestore call is wrapped in `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger("fasal_kavach.db")

# ---------------------------------------------------------------------------
# Collection names — must match firestore.rules exactly.
# If you rename one here, rename it there too, or the rules stop applying.
# ---------------------------------------------------------------------------
COL_FARMS = "farms"
COL_ADVISORIES = "advisories"
COL_EVENTS = "risk_events"
COL_WEATHER = "weather_cache"
COL_FEEDBACK = "feedback"
COL_USERS = "users"


# ===========================================================================
# Backend 1 — in memory. Tests and offline development.
# ===========================================================================
class MemoryBackend:
    """Dict-backed store. Same interface as Firestore, no persistence."""

    name = "memory"

    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict]] = {}

    def _col(self, collection: str) -> dict[str, dict]:
        return self._data.setdefault(collection, {})

    async def set(self, collection: str, doc_id: str, data: dict) -> None:
        self._col(collection)[doc_id] = dict(data)

    async def get(self, collection: str, doc_id: str) -> dict | None:
        doc = self._col(collection).get(doc_id)
        return dict(doc) if doc is not None else None

    async def update(self, collection: str, doc_id: str, patch: dict) -> dict | None:
        doc = self._col(collection).get(doc_id)
        if doc is None:
            return None
        doc.update(patch)
        return dict(doc)

    async def list(self, collection: str, limit: int | None = None) -> list[dict]:
        docs = [dict(d) for d in self._col(collection).values()]
        return docs[:limit] if limit else docs

    async def query(
        self, collection: str, field: str, value: Any, limit: int | None = None
    ) -> list[dict]:
        docs = [dict(d) for d in self._col(collection).values() if d.get(field) == value]
        return docs[:limit] if limit else docs

    async def add(self, collection: str, data: dict) -> str:
        doc_id = f"m_{len(self._col(collection)) + 1:06d}"
        self._col(collection)[doc_id] = dict(data)
        return doc_id

    async def count(self, collection: str) -> int:
        return len(self._col(collection))

    def clear(self) -> None:
        self._data.clear()


# ===========================================================================
# Backend 2 — real Firestore.
# ===========================================================================
class FirestoreBackend:
    """
    Firestore via the Admin SDK.

    The Admin SDK runs with a service account, which means it BYPASSES
    firestore.rules entirely. Those rules protect direct browser access.
    Ownership checks for API requests happen in auth.py instead.
    """

    name = "firestore"

    def __init__(self, client: Any) -> None:
        self._db = client

    # -- sync helpers, each run in a worker thread ---------------------------
    def _set_sync(self, collection: str, doc_id: str, data: dict) -> None:
        self._db.collection(collection).document(doc_id).set(data)

    def _get_sync(self, collection: str, doc_id: str) -> dict | None:
        snap = self._db.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def _update_sync(self, collection: str, doc_id: str, patch: dict) -> dict | None:
        ref = self._db.collection(collection).document(doc_id)
        snap = ref.get()
        if not snap.exists:
            return None
        ref.update(patch)
        return ref.get().to_dict()

    def _list_sync(self, collection: str, limit: int | None) -> list[dict]:
        q = self._db.collection(collection)
        if limit:
            q = q.limit(limit)
        return [d.to_dict() for d in q.stream()]

    def _query_sync(
        self, collection: str, field: str, value: Any, limit: int | None
    ) -> list[dict]:
        col = self._db.collection(collection)
        # FieldFilter is the modern API; the positional form is deprecated but
        # still works on older google-cloud-firestore. Try new, fall back.
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter

            q = col.where(filter=FieldFilter(field, "==", value))
        except Exception:  # pragma: no cover - depends on installed version
            q = col.where(field, "==", value)
        if limit:
            q = q.limit(limit)
        return [d.to_dict() for d in q.stream()]

    def _add_sync(self, collection: str, data: dict) -> str:
        _, ref = self._db.collection(collection).add(data)
        return ref.id

    # -- async interface ----------------------------------------------------
    async def set(self, collection: str, doc_id: str, data: dict) -> None:
        await asyncio.to_thread(self._set_sync, collection, doc_id, dict(data))

    async def get(self, collection: str, doc_id: str) -> dict | None:
        return await asyncio.to_thread(self._get_sync, collection, doc_id)

    async def update(self, collection: str, doc_id: str, patch: dict) -> dict | None:
        return await asyncio.to_thread(self._update_sync, collection, doc_id, dict(patch))

    async def list(self, collection: str, limit: int | None = None) -> list[dict]:
        return await asyncio.to_thread(self._list_sync, collection, limit)

    async def query(
        self, collection: str, field: str, value: Any, limit: int | None = None
    ) -> list[dict]:
        return await asyncio.to_thread(self._query_sync, collection, field, value, limit)

    async def add(self, collection: str, data: dict) -> str:
        return await asyncio.to_thread(self._add_sync, collection, dict(data))

    async def count(self, collection: str) -> int:
        docs = await self.list(collection)
        return len(docs)

    def clear(self) -> None:
        raise RuntimeError("Refusing to wipe a real Firestore database from code.")


# ===========================================================================
# Backend selection
# ===========================================================================
_backend: MemoryBackend | FirestoreBackend | None = None


def init(force_memory: bool = False) -> str:
    """
    Choose a backend once, at startup. Returns the backend name.

    Firestore is used when ALL of these hold:
      - USE_FIRESTORE is not "false"
      - firebase-admin imports
      - credentials resolve (GOOGLE_APPLICATION_CREDENTIALS, or the
        service account Cloud Run injects automatically)

    Anything missing falls back to memory with a loud warning. The demo
    still runs; it just will not survive a restart.
    """
    global _backend

    if force_memory or os.getenv("USE_FIRESTORE", "true").lower() == "false":
        _backend = MemoryBackend()
        logger.warning('{"event": "db_backend", "backend": "memory", "reason": "disabled_by_env"}')
        return _backend.name

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
            if cred_path and os.path.exists(cred_path):
                # Local development: explicit service-account JSON file.
                firebase_admin.initialize_app(credentials.Certificate(cred_path))
            else:
                # Cloud Run: the runtime service account is picked up here.
                firebase_admin.initialize_app()

        client = firestore.client()
        _backend = FirestoreBackend(client)
        logger.info('{"event": "db_backend", "backend": "firestore"}')
        return _backend.name

    except Exception as exc:
        _backend = MemoryBackend()
        reason = str(exc).replace('"', "'")[:200]
        logger.warning(
            f'{{"event": "db_backend", "backend": "memory", "reason": "{reason}"}}'
        )
        return _backend.name


def get_backend() -> MemoryBackend | FirestoreBackend:
    """Lazy init so imports in tests never require Firebase."""
    global _backend
    if _backend is None:
        _backend = MemoryBackend()
    return _backend


def backend_name() -> str:
    return get_backend().name


def reset_for_tests() -> None:
    """Wipe the in-memory store between tests. No-op safety on Firestore."""
    global _backend
    _backend = MemoryBackend()


# ===========================================================================
# Domain functions — what the routers actually call.
# Routers should never touch get_backend() directly.
# ===========================================================================

# -- farms ------------------------------------------------------------------
async def save_farm(farm: dict) -> None:
    await get_backend().set(COL_FARMS, farm["farm_id"], farm)


async def get_farm(farm_id: str) -> dict | None:
    return await get_backend().get(COL_FARMS, farm_id)


async def update_farm(farm_id: str, patch: dict) -> dict | None:
    return await get_backend().update(COL_FARMS, farm_id, patch)


async def list_farms(limit: int | None = None) -> list[dict]:
    return await get_backend().list(COL_FARMS, limit)


async def farms_for_owner(owner_uid: str) -> list[dict]:
    return await get_backend().query(COL_FARMS, "owner_uid", owner_uid)


# -- advisories -------------------------------------------------------------
async def save_advisory(advisory: dict) -> None:
    await get_backend().set(COL_ADVISORIES, advisory["advisory_id"], advisory)


async def get_advisory(advisory_id: str) -> dict | None:
    return await get_backend().get(COL_ADVISORIES, advisory_id)


async def advisories_for_farm(farm_id: str) -> list[dict]:
    """
    Newest first. In Firestore this needs a composite index on
    (farm_id ASC, created_at DESC) if you ever move the sort server-side;
    for demo volumes sorting in Python is cheaper than managing the index.
    """
    docs = await get_backend().query(COL_ADVISORIES, "farm_id", farm_id)
    docs.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    return docs


async def all_advisories() -> list[dict]:
    return await get_backend().list(COL_ADVISORIES)


# -- risk events ------------------------------------------------------------
async def save_event(event: dict) -> None:
    await get_backend().set(COL_EVENTS, event["event_id"], event)


async def get_event(event_id: str) -> dict | None:
    if not event_id:
        return None
    return await get_backend().get(COL_EVENTS, event_id)


# -- weather ----------------------------------------------------------------
async def save_weather(key: str, data: dict) -> None:
    """Document id is "{grid_id}_{date}"; grid_id is also a field so we
    can query by cell instead of scanning keys by prefix."""
    payload = dict(data)
    payload.setdefault("grid_id", key.split("_")[0])
    await get_backend().set(COL_WEATHER, key, payload)


async def weather_for_grid(grid_id: str) -> list[dict]:
    docs = await get_backend().query(COL_WEATHER, "grid_id", grid_id)
    docs.sort(key=lambda w: w.get("date", ""))
    return docs


# -- feedback ---------------------------------------------------------------
async def save_feedback(feedback: dict) -> str:
    return await get_backend().add(COL_FEEDBACK, feedback)


async def count_farms() -> int:
    return await get_backend().count(COL_FARMS)
