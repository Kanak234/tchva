"""
Auth tests — Section 28

The point of these: prove that with DEMO_MODE off, an unauthenticated
request is rejected and one user cannot read another user's farm.

A judge will ask "what stops me reading someone else's data?" These
tests are the answer you can point at.
"""

import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import auth  # noqa: E402


class TestBearerExtraction:
    def test_valid_bearer(self):
        assert auth._extract_bearer("Bearer abc.def.ghi") == "abc.def.ghi"

    def test_case_insensitive_scheme(self):
        assert auth._extract_bearer("bearer abc") == "abc"

    def test_missing_header(self):
        assert auth._extract_bearer(None) is None

    def test_wrong_scheme(self):
        assert auth._extract_bearer("Basic abc") is None

    def test_no_token_after_scheme(self):
        assert auth._extract_bearer("Bearer   ") is None


class TestCurrentUid:
    @pytest.mark.asyncio
    async def test_demo_mode_allows_anonymous(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        assert await auth.current_uid(None) == auth.DEMO_UID

    @pytest.mark.asyncio
    async def test_no_demo_mode_rejects_anonymous(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "false")
        with pytest.raises(HTTPException) as exc:
            await auth.current_uid(None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_garbage_token_rejected_without_demo_mode(self, monkeypatch):
        """An unverifiable token must not be trusted."""
        monkeypatch.setenv("DEMO_MODE", "false")
        with pytest.raises(HTTPException) as exc:
            await auth.current_uid("Bearer not-a-real-token")
        assert exc.value.status_code == 401


class TestOwnership:
    def test_owner_matches(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "false")
        assert auth.owns({"owner_uid": "uid_alice"}, "uid_alice") is True

    def test_other_user_denied(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "false")
        assert auth.owns({"owner_uid": "uid_alice"}, "uid_bob") is False

    def test_missing_farm_denied(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "false")
        assert auth.owns(None, "uid_alice") is False

    def test_demo_prefix_shared_only_in_demo_mode(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        assert auth.owns({"owner_uid": "demo_user_3"}, "demo_user") is True
        monkeypatch.setenv("DEMO_MODE", "false")
        assert auth.owns({"owner_uid": "demo_user_3"}, "demo_user") is False

    def test_demo_mode_does_not_expose_real_accounts(self, monkeypatch):
        """Demo mode must never open up a genuine phone-auth account."""
        monkeypatch.setenv("DEMO_MODE", "true")
        assert auth.owns({"owner_uid": "aBcXyZ123realuid"}, "demo_user") is False

    def test_require_owner_raises_404_then_403(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "false")
        with pytest.raises(HTTPException) as missing:
            auth.require_owner(None, "uid_alice")
        assert missing.value.status_code == 404

        with pytest.raises(HTTPException) as forbidden:
            auth.require_owner({"owner_uid": "uid_bob"}, "uid_alice")
        assert forbidden.value.status_code == 403
