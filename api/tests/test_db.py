"""
Storage layer tests — Section 28

These run against the in-memory backend, which is the SAME interface the
Firestore backend implements. That is the point of db.py: if these pass,
the contract the routers depend on is intact regardless of which backend
is selected at startup.

What these do NOT prove: that real Firestore is reachable and that the
service account has permission. Nothing here can prove that. Run
`GET /internal/status` against the deployed service and confirm it
reports "firestore" before you demo.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_store():
    db.reset_for_tests()
    yield
    db.reset_for_tests()


FARM = {
    "farm_id": "f_test_01",
    "owner_uid": "uid_alice",
    "village": "Barhi",
    "grid_id": "HZB-01",
    "lat": 24.0,
    "lon": 85.25,
    "crop": "paddy",
    "sowing_date": "2026-07-01",
    "area_ha": 1.0,
    "irrigation": "rainfed",
    "language": "hi",
    "active": True,
    "created_at": "2026-07-01T09:00:00",
}


class TestFarms:
    @pytest.mark.asyncio
    async def test_save_and_get_roundtrip(self):
        await db.save_farm(FARM)
        got = await db.get_farm("f_test_01")
        assert got is not None
        assert got["village"] == "Barhi"
        assert got["owner_uid"] == "uid_alice"

    @pytest.mark.asyncio
    async def test_missing_farm_returns_none(self):
        assert await db.get_farm("f_nope") is None

    @pytest.mark.asyncio
    async def test_update_applies_patch(self):
        await db.save_farm(FARM)
        updated = await db.update_farm("f_test_01", {"crop": "maize"})
        assert updated["crop"] == "maize"
        assert updated["village"] == "Barhi"  # untouched fields survive

    @pytest.mark.asyncio
    async def test_update_missing_farm_returns_none(self):
        assert await db.update_farm("f_nope", {"crop": "maize"}) is None

    @pytest.mark.asyncio
    async def test_farms_scoped_to_owner(self):
        await db.save_farm(FARM)
        await db.save_farm({**FARM, "farm_id": "f_test_02", "owner_uid": "uid_bob"})
        alice = await db.farms_for_owner("uid_alice")
        assert [f["farm_id"] for f in alice] == ["f_test_01"]

    @pytest.mark.asyncio
    async def test_returned_doc_is_a_copy(self):
        """Mutating a returned dict must not corrupt the store."""
        await db.save_farm(FARM)
        got = await db.get_farm("f_test_01")
        got["village"] = "CORRUPTED"
        again = await db.get_farm("f_test_01")
        assert again["village"] == "Barhi"


class TestAdvisories:
    @pytest.mark.asyncio
    async def test_advisories_filtered_by_farm_and_sorted(self):
        await db.save_advisory(
            {"advisory_id": "a1", "farm_id": "f1", "created_at": "2026-08-01T00:00:00"}
        )
        await db.save_advisory(
            {"advisory_id": "a2", "farm_id": "f1", "created_at": "2026-08-05T00:00:00"}
        )
        await db.save_advisory(
            {"advisory_id": "a3", "farm_id": "f2", "created_at": "2026-08-09T00:00:00"}
        )
        got = await db.advisories_for_farm("f1")
        assert [a["advisory_id"] for a in got] == ["a2", "a1"]  # newest first

    @pytest.mark.asyncio
    async def test_same_id_overwrites_not_duplicates(self):
        """Re-running ingest must not pile up duplicate advisories."""
        await db.save_advisory({"advisory_id": "a1", "farm_id": "f1", "headline": "v1"})
        await db.save_advisory({"advisory_id": "a1", "farm_id": "f1", "headline": "v2"})
        got = await db.advisories_for_farm("f1")
        assert len(got) == 1
        assert got[0]["headline"] == "v2"


class TestWeather:
    @pytest.mark.asyncio
    async def test_grid_id_derived_from_key(self):
        await db.save_weather("HZB-01_2026-08-19", {"date": "2026-08-19", "rain_mm": 12.0})
        got = await db.weather_for_grid("HZB-01")
        assert len(got) == 1
        assert got[0]["rain_mm"] == 12.0

    @pytest.mark.asyncio
    async def test_sorted_by_date_and_scoped_to_grid(self):
        await db.save_weather("HZB-01_2026-08-20", {"date": "2026-08-20", "grid_id": "HZB-01"})
        await db.save_weather("HZB-01_2026-08-18", {"date": "2026-08-18", "grid_id": "HZB-01"})
        await db.save_weather("HZB-02_2026-08-19", {"date": "2026-08-19", "grid_id": "HZB-02"})
        got = await db.weather_for_grid("HZB-01")
        assert [w["date"] for w in got] == ["2026-08-18", "2026-08-20"]


class TestEventsAndFeedback:
    @pytest.mark.asyncio
    async def test_event_roundtrip(self):
        await db.save_event({"event_id": "e1", "evidence": {"rain_mm_next_48h": 61.4}})
        got = await db.get_event("e1")
        assert got["evidence"]["rain_mm_next_48h"] == 61.4

    @pytest.mark.asyncio
    async def test_empty_event_id_is_safe(self):
        assert await db.get_event("") is None

    @pytest.mark.asyncio
    async def test_feedback_gets_generated_id(self):
        fid = await db.save_feedback({"advisory_id": "a1", "helpful": True})
        assert isinstance(fid, str) and fid


class TestBackendSelection:
    def test_defaults_to_memory_without_credentials(self):
        assert db.init(force_memory=True) == "memory"
        assert db.backend_name() == "memory"

    def test_env_flag_disables_firestore(self, monkeypatch):
        monkeypatch.setenv("USE_FIRESTORE", "false")
        assert db.init() == "memory"
