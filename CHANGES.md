# What Changed — persistence, auth, and CI

Three defects were blocking submission. All three are fixed. Nothing was
rewritten from scratch; your rules engine, AI client, templates, screens
and tests are untouched except where the fix required it.

Test count went from **46 to 88**.

---

## 1. Persistence — CRITICAL, now fixed

**The bug.** `firebase-admin` was in `requirements.txt` and
`firestore.rules` existed, but there was no Firestore code anywhere in
`api/`. Storage was four module-level Python dicts:

```python
api/routers/farms.py:32       _farms
api/routers/advisories.py:29  _advisories, _events, _weather_cache, _feedback
```

On Cloud Run that fails two ways. Scale-to-zero kills the container and
every dict with it — a judge who creates a farm, waits ten minutes and
reloads gets a 404. And under load, container A holds the farm while
container B answers the next request and has never seen it.

**The fix.** One new file, `api/db.py`, with two backends behind one
interface:

- `FirestoreBackend` — real Firestore, used when credentials resolve
- `MemoryBackend` — dicts, used in tests and when they do not

Routers never know which is running. That is deliberate: `pytest` needs
no Firebase project, and the same code path runs in production.

`firebase-admin` is synchronous. Calling it directly inside an `async def`
route would block the event loop and stall every other request, so every
Firestore call goes through `asyncio.to_thread`.

**Files:** `api/db.py` (new), `api/main.py`, `api/routers/farms.py`,
`api/routers/advisories.py`, `api/routers/ask.py`,
`api/routers/internal.py`

**New endpoint — check this before every demo:**

```bash
curl https://<your-url>/internal/status
# {"backend": "firestore", "persistent": true, "farms_stored": 12}
```

If it says `memory`, credentials did not resolve and your data will
vanish. `/healthz` reports the same thing.

---

## 2. Authentication — CRITICAL, now fixed

**The bug.** `farms.py:86` hardcoded `owner_uid="demo_user"`. There was no
login screen. `firebase.ts` exported `signInWithPhoneNumber` and nothing
ever called it.

So `firestore.rules` was decorative — the rules check
`request.auth.uid`, and there was no auth to check. Any farm id read any
farmer's advisories. Judge question 11 — *"what data are you storing about
farmers, and where?"* — answered "in a dict, unauthenticated."

**The fix.** Real Firebase phone OTP, end to end.

- `api/auth.py` (new) — verifies the Firebase ID token against Google's
  public keys, extracts the uid, enforces ownership
- `web/src/lib/auth.ts` (new) — OTP send/confirm, token retrieval,
  sign-out, error messages written as sentences rather than codes
- `web/src/app/login/page.tsx` (new) — phone → OTP, one field per screen,
  30-second resend cooldown
- `web/src/lib/api.ts` — attaches `Authorization: Bearer <token>` to every
  request. Because all traffic already went through one `req()` function,
  this was a four-line change and no route can forget it.
- `GET /api/v1/me/farms` (new) — finds your farm after signing in on a new
  device. `localStorage` is now a cache, not the source of truth.

**Demo mode is kept, but labelled.** `DEMO_MODE=true` accepts
unauthenticated calls as `demo_user`. Judges tap through without waiting
for an SMS. Say this out loud on stage — the honest version survives
questioning, a silent bypass does not. Set `DEMO_MODE=false` and it is
gone; `test_auth.py` proves it.

One deliberate detail: in demo mode, `owns()` allows access between
`demo_user*` accounts only. A real phone-auth uid can never be reached
that way, and there is a test for exactly that.

---

## 3. CI locale check — fixed

**The bug.** The job ran `require('./web/src/lib/i18n.ts')`. Node cannot
`require()` TypeScript. It threw, and `|| {}` does not catch a throw — it
only handles a falsy return. The job failed on every push and never
checked a single key. A red tick nobody trusts is worse than no tick.

**The fix.** `scripts/check_locale_keys.py` parses the four language
blocks and diffs each against English. It found **18 keys missing from
both Khortha and Bengali** — those are now written. Four locales, 64 keys
each, all present.

Also in CI: a `build-frontend` job running `tsc --noEmit`, and
`USE_FIRESTORE=false` pinned on the test job so the suite never needs
cloud credentials.

---

## 4. Number containment — tightened

`validate_advisory` whitelisted `{0,1,2,3,4,5,6,7}` as always-safe. That
let a hallucinated **"apply 5 kg per acre"** through the gate — exactly
the failure this project claims to have designed out.

Now the safe set is drawn from the whole event (evidence, thresholds,
window dates) plus only `{1,2,3}` for the three numbered actions. A model
inventing a quantity gets rejected.

---

## 5. Seed data — moved out of code

Twelve synthetic farms lived inline in `internal.py`. They now live in
`data/seed/demo_farms.json`, which `data/README.md` already pointed at.

The file carries its own `_provenance` block stating plainly that the
farms are invented, that the villages and coordinates are real, and that
**the weather is not synthetic** — every rainfall and temperature figure
the rules act on is fetched live from Open-Meteo.

The sowing dates are chosen so the twelve farms sit in ten different
growth stages across all four grid cells, which exercises every branch of
the crop calendar in a single ingest run.

**One agronomic correction:** the old seed had wheat sown in July. Wheat
is a rabi crop, sown November–December. In an August demo that is wrong,
and an agriculture judge would catch it. That farm is now tomato; wheat
and frost rules stay covered by the test suite.

---

## 6. Dockerfile — a bug you had not hit yet

`internal.py` resolved the seed path relative to the repo layout. Inside
the image, `api/` is copied to `/app` and `data/` to `/app/data`, so the
same expression pointed at `/data/seed/...` and found nothing — silently.
The seed would have returned zero farms and the deployed demo would have
been empty.

Path resolution now tries every layout, and the Dockerfile asserts the
data files are present at build time rather than failing at 2am.

---

## What I could not verify

**I have no Firebase project and no credentials, so nothing here has
touched real Firestore.** What is proven: 88 tests pass, ruff is clean,
`tsc --noEmit` is clean, and the API works end to end on the in-memory
backend.

What is not proven, and only you can prove: that Firestore actually
connects. `FIREBASE_SETUP.md` walks through it — fifteen minutes, console
only, no code. The verification step to trust is seeding twelve farms,
restarting the server, and seeing `farms_stored: 12` still there. Before
this fix that number was 0.

The frontend production build also could not run here — Next.js fetches
the Inter font from Google Fonts and my sandbox blocks that domain. It
will build on your machine. `tsc --noEmit` passing means the TypeScript
is sound.

---

## Read these two files yourself

Judges will ask where farmer data is stored and what stops one user
reading another's. You have to answer that, not me. Both files are
commented specifically so you can:

- `api/db.py` — why Firestore, why two backends, why `to_thread`
- `api/auth.py` — how the token check works, and what demo mode does

The two tests worth being able to point at:

```
test_auth.py::TestOwnership::test_demo_mode_does_not_expose_real_accounts
test_api_flow.py::TestAuthEnforcement::test_cannot_read_another_users_farm
```

---

## Still open, and not code

1. **Team names.** Four `[NAME]` placeholders in the build spec. Roster
   locks **24 Aug 2026**.
2. **Member 2 (frontend) unassigned.** 43 hours of work, and the demo
   lives there.
3. **§34 Q1 of the spec.** Does edition 2 use MP-submitted problem
   statements the way edition 1 did, or open themes? If problem
   statements, the framing must name a specific one. The engineering is
   unaffected either way — but check before submitting.
