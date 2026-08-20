"""
auth.py — Who is making this request?

WHY THIS FILE EXISTS
--------------------
Before this file, every farm was created with owner_uid="demo_user" and
any request could read any farm by guessing its id. That made
firestore.rules decorative: the rules check request.auth.uid, and there
was no auth to check.

HOW IT WORKS
------------
The browser signs in with a phone number and OTP (Firebase Auth). Firebase
hands the browser a signed ID token, valid one hour. Every API call sends
it as:

    Authorization: Bearer <token>

This file verifies the signature against Google's public keys and pulls
the uid out. A forged token fails verification — the client cannot lie
about who it is.

DEMO MODE
---------
DEMO_MODE=true accepts unauthenticated requests as the fixed uid
"demo_user". This exists so the pitch does not depend on OTP SMS
arriving on stage, and so seeded demo farms are reachable.

Say this out loud to judges rather than hiding it. The honest version —
"demo mode is a labelled environment flag, and here is the real phone
sign-in working" — survives questioning. A silent bypass does not.
Set DEMO_MODE=false and the bypass is gone.
"""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger("fasal_kavach.auth")

DEMO_UID = "demo_user"


def demo_mode() -> bool:
    return os.getenv("DEMO_MODE", "false").lower() == "true"


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def _verify_sync(token: str) -> dict:
    """Verify an ID token with the Admin SDK. Raises on anything invalid."""
    import firebase_admin
    from firebase_admin import auth as fb_auth

    if not firebase_admin._apps:
        # db.init() normally does this. If storage fell back to memory,
        # there is no app, and no token can be verified.
        raise RuntimeError("Firebase app not initialised")

    return fb_auth.verify_id_token(token)


async def verify_token(token: str) -> dict | None:
    """Return decoded claims, or None if the token is not usable."""
    try:
        return await asyncio.to_thread(_verify_sync, token)
    except Exception as exc:
        reason = str(exc).replace('"', "'")[:200]
        logger.warning(f'{{"event": "token_verify_failed", "reason": "{reason}"}}')
        return None


async def current_uid(authorization: str | None = Header(default=None)) -> str:
    """
    FastAPI dependency. Returns the caller's uid.

    - Valid token            -> the real uid
    - No/!valid + DEMO_MODE  -> "demo_user"
    - No/!valid otherwise    -> 401
    """
    token = _extract_bearer(authorization)

    if token:
        claims = await verify_token(token)
        if claims and claims.get("uid"):
            return claims["uid"]
        if claims and claims.get("sub"):
            return claims["sub"]

    if demo_mode():
        return DEMO_UID

    raise HTTPException(
        status_code=401,
        detail={
            "code": "UNAUTHENTICATED",
            "message": "Sign in with Google to continue.",
        },
    )


async def optional_uid(authorization: str | None = Header(default=None)) -> str | None:
    """Same as current_uid but returns None instead of raising."""
    token = _extract_bearer(authorization)
    if token:
        claims = await verify_token(token)
        if claims:
            return claims.get("uid") or claims.get("sub")
    return DEMO_UID if demo_mode() else None


def owns(farm: dict | None, uid: str) -> bool:
    """
    Ownership check for API requests.

    Note the demo escape: in DEMO_MODE the seeded farms belong to
    demo_user_2..6, and a judge tapping through the demo is demo_user.
    Rather than reassign the seed data, demo mode allows reads of any
    farm whose owner_uid starts with "demo_user". Real accounts are
    never covered by that prefix.
    """
    if not farm:
        return False
    owner = farm.get("owner_uid", "")
    if owner == uid:
        return True
    if demo_mode() and owner.startswith(DEMO_UID) and uid.startswith(DEMO_UID):
        return True
    return False


def require_owner(farm: dict | None, uid: str) -> None:
    """Raise the right error: 404 if missing, 403 if someone else's."""
    if farm is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Farm not found."},
        )
    if not owns(farm, uid):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FORBIDDEN",
                "message": "This farm belongs to another account.",
            },
        )
