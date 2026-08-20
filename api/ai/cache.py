"""
Advisory cache — Section 19.3

Cache key buckets the driving number so similar values share a cache entry.
Stored in-memory for the prototype; Firestore collection in production.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("fasal_kavach.ai.cache")

# In-memory cache for the prototype
_cache: dict[str, dict] = {}
_cache_timestamps: dict[str, datetime] = {}
CACHE_TTL = timedelta(days=7)


def bucket(mm: float) -> str:
    """Round the driving number into a band for cache key generation."""
    b = int(mm // 20) * 20
    return f"{b}-{b + 20}"


def cache_key(
    rule_id: str,
    crop: str,
    stage_name: str,
    severity: str,
    language: str,
    evidence: dict,
) -> str:
    """
    Build a cache key from the advisory parameters.

    evidence_bucket rounds the driving number so that
    61.4 mm and 63.1 mm share a cache entry but 61.4 and 120 do not.
    """
    # Find the driving number (first numeric value in evidence)
    driving_number = 0.0
    for v in evidence.values():
        if isinstance(v, int | float):
            driving_number = float(v)
            break

    evidence_b = bucket(driving_number)
    raw = f"{rule_id}|{crop}|{stage_name}|{severity}|{language}|{evidence_b}"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


def get(key: str) -> dict | None:
    """Retrieve a cached advisory, respecting TTL."""
    if key not in _cache:
        return None

    ts = _cache_timestamps.get(key)
    if ts and datetime.now() - ts > CACHE_TTL:
        del _cache[key]
        del _cache_timestamps[key]
        return None

    logger.info(f"Cache HIT: {key}")
    return _cache[key]


def put(key: str, advisory: dict) -> None:
    """Store an advisory in the cache."""
    _cache[key] = advisory
    _cache_timestamps[key] = datetime.now()
    logger.info(f"Cache PUT: {key}")


def stats() -> dict:
    """Return cache statistics."""
    return {
        "size": len(_cache),
        "keys": list(_cache.keys())[:10],
    }
