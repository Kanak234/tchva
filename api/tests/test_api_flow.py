"""
End-to-end API tests — Section 28

These drive the real FastAPI app through TestClient, on the in-memory
backend. They cover the two questions a judge is most likely to ask:

  "What happens if I hit your API without logging in?"
  "What stops me reading another farmer's data?"

Run with: pytest tests/test_api_flow.py -v
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402

os.environ["USE_FIRESTORE"] = "false"

import main  # noqa: E402

NEW_FARM = {
    "village": "Barhi",
    "lat": 24.00,
    "lon": 85.25,
    "crop": "paddy",
    "sowing_date": "2026-07-01",
    "area_ha": 1.0,
    "irrigation": "rainfed",
    "language": "hi",
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("USE_FIRESTORE", "false")
    db.reset_for_tests()
    with TestClient(main.app) as c:
        yield c
    db.reset_for_tests()


class TestHealth:
    def test_healthz_reports_storage_backend(self, client):
        body = client.get("/healthz").json()
        assert body["status"] == "ok"
        # Tells you at a glance whether you are about to demo on
        # storage that forgets everything.
        assert body["storage"] in ("memory", "firestore")

    def test_internal_status_flags_non_persistent_storage(self, client):
        body = client.get("/internal/status").json()
        assert body["persistent"] is False
        assert body["seed_file_found"] is True


class TestFarmLifecycle:
    def test_create_read_update(self, client):
        created = client.post("/api/v1/farms", json=NEW_FARM)
        assert created.status_code == 201
        farm_id = created.json()["farm_id"]
        assert created.json()["grid_id"] == "HZB-01"

        read = client.get(f"/api/v1/farms/{farm_id}")
        assert read.status_code == 200
        assert read.json()["village"] == "Barhi"
        assert read.json()["days_after_sowing"] > 0

        patched = client.patch(f"/api/v1/farms/{farm_id}", json={"language": "kho"})
        assert patched.status_code == 200
        assert patched.json()["language"] == "kho"

    def test_farm_survives_across_requests(self, client):
        """The bug this whole storage layer exists to kill."""
        farm_id = client.post("/api/v1/farms", json=NEW_FARM).json()["farm_id"]
        for _ in range(3):
            assert client.get(f"/api/v1/farms/{farm_id}").status_code == 200

    def test_outside_coverage_rejected(self, client):
        body = {**NEW_FARM, "lat": 19.07, "lon": 72.87}  # Mumbai
        res = client.post("/api/v1/farms", json=body)
        assert res.status_code == 400
        assert res.json()["detail"]["code"] == "OUTSIDE_COVERAGE"

    def test_unknown_farm_is_404(self, client):
        assert client.get("/api/v1/farms/f_does_not_exist").status_code == 404


class TestSeeding:
    def test_seed_is_idempotent(self, client):
        first = client.post("/internal/seed").json()
        assert first["status"] == "seeded"
        assert first["count"] == 12

        second = client.post("/internal/seed").json()
        assert second["status"] == "already_seeded"
        assert second["count"] == 12

    def test_seeded_farms_cover_all_grid_cells(self, client):
        client.post("/internal/seed")
        from routers.internal import load_demo_farms

        grids = {f["grid_id"] for f in load_demo_farms()}
        assert grids == {"HZB-01", "HZB-02", "HZB-03", "HZB-04"}

    def test_seed_farms_carry_no_annotation_keys(self, client):
        """The _stage_intent notes are for the team, not the Farm model."""
        from routers.internal import load_demo_farms

        for farm in load_demo_farms():
            assert not any(k.startswith("_") for k in farm)


class TestAuthEnforcement:
    def test_anonymous_rejected_when_demo_mode_off(self, client, monkeypatch):
        farm_id = client.post("/api/v1/farms", json=NEW_FARM).json()["farm_id"]

        monkeypatch.setenv("DEMO_MODE", "false")
        res = client.get(f"/api/v1/farms/{farm_id}")
        assert res.status_code == 401

    def test_cannot_read_another_users_farm(self, client, monkeypatch):
        """
        Create as demo_user, then pretend to be a different real account.
        Without the ownership check this returned 200 and leaked the farm.
        """
        farm_id = client.post("/api/v1/farms", json=NEW_FARM).json()["farm_id"]

        monkeypatch.setenv("DEMO_MODE", "false")
        monkeypatch.setattr(
            "auth.verify_token", _fake_verify("someone_elses_real_uid")
        )
        res = client.get(
            f"/api/v1/farms/{farm_id}", headers={"Authorization": "Bearer x.y.z"}
        )
        assert res.status_code == 403

    def test_cannot_read_another_users_advisories(self, client, monkeypatch):
        farm_id = client.post("/api/v1/farms", json=NEW_FARM).json()["farm_id"]

        monkeypatch.setenv("DEMO_MODE", "false")
        monkeypatch.setattr(
            "auth.verify_token", _fake_verify("someone_elses_real_uid")
        )
        res = client.get(
            f"/api/v1/farms/{farm_id}/advisories",
            headers={"Authorization": "Bearer x.y.z"},
        )
        assert res.status_code == 403

    def test_owner_can_read_own_farm_with_token(self, client, monkeypatch):
        farm_id = client.post("/api/v1/farms", json=NEW_FARM).json()["farm_id"]

        monkeypatch.setenv("DEMO_MODE", "false")
        # demo_user created it; sign in as demo_user for real.
        monkeypatch.setattr("auth.verify_token", _fake_verify("demo_user"))
        res = client.get(
            f"/api/v1/farms/{farm_id}", headers={"Authorization": "Bearer x.y.z"}
        )
        assert res.status_code == 200


def _fake_verify(uid: str):
    """Stand in for Google's token verification, which needs a live project."""

    async def _verify(_token: str):
        return {"uid": uid}

    return _verify
