"""
Internal endpoint authorisation.

/internal/seed can rewrite the whole dataset, so the guard in front of it
is worth pinning. The failure mode these tests exist to prevent is not a
crash — it is the quiet one, where a missing environment variable turns
the lock off and nothing anywhere reports it.
"""

import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from routers.internal import _check_token  # noqa: E402


def _prod(monkeypatch, token: str | None):
    monkeypatch.setenv("DEMO_MODE", "false")
    if token is None:
        monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    else:
        monkeypatch.setenv("INTERNAL_TOKEN", token)


class TestDemoMode:
    def test_demo_mode_allows_no_token(self, monkeypatch):
        """The on-stage 'Run now' button has no header to send."""
        monkeypatch.setenv("DEMO_MODE", "true")
        _check_token(None)

    def test_demo_mode_is_the_default(self, monkeypatch):
        monkeypatch.delenv("DEMO_MODE", raising=False)
        _check_token(None)


class TestProductionMode:
    def test_missing_token_config_refuses(self, monkeypatch):
        """
        The regression that matters. Previously an unset INTERNAL_TOKEN
        skipped the check, so a deploy that forgot the secret exposed
        /internal/seed to anyone. It must now refuse to serve.
        """
        _prod(monkeypatch, None)
        with pytest.raises(HTTPException) as exc:
            _check_token(None)
        assert exc.value.status_code == 503

    def test_empty_token_config_refuses(self, monkeypatch):
        _prod(monkeypatch, "")
        with pytest.raises(HTTPException) as exc:
            _check_token("anything")
        assert exc.value.status_code == 503

    def test_correct_token_passes(self, monkeypatch):
        _prod(monkeypatch, "s3cret")
        _check_token("s3cret")

    def test_wrong_token_is_forbidden(self, monkeypatch):
        _prod(monkeypatch, "s3cret")
        with pytest.raises(HTTPException) as exc:
            _check_token("guess")
        assert exc.value.status_code == 403

    def test_absent_header_is_forbidden(self, monkeypatch):
        _prod(monkeypatch, "s3cret")
        with pytest.raises(HTTPException) as exc:
            _check_token(None)
        assert exc.value.status_code == 403

    def test_prefix_of_token_is_forbidden(self, monkeypatch):
        _prod(monkeypatch, "s3cret")
        with pytest.raises(HTTPException) as exc:
            _check_token("s3c")
        assert exc.value.status_code == 403
