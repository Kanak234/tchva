# Firebase Setup — do this once, takes about 15 minutes

This is the only part of the fix that cannot be written for you. The code
is done; it needs a project to point at.

You will not write any code here. Six steps, console only.

---

## Before you start

You need a Google account. You do **not** need a credit card, and you will
not be asked for one. Everything below stays inside the Spark (free) plan.

---

## Step 1 — Create the project

1. Go to <https://console.firebase.google.com>
2. **Add project**
3. Name it `fasal-kavach`
4. Google Analytics: **turn it off**. It adds a consent surface you would
   then have to explain to judges, for data you are not going to use.
5. Create.

---

## Step 2 — Create the Firestore database

1. Left sidebar → **Build** → **Firestore Database** → **Create database**
2. Location: **asia-south1 (Mumbai)**

   This one is not cosmetic. A judge will ask where farmer data is stored.
   "In Mumbai, on Indian infrastructure" is a real answer. It is also
   **permanent** — the region cannot be changed after creation. Get it
   right the first time.
3. Start in **production mode**. Your `firestore.rules` file already
   contains the real rules; test mode would silently allow everything for
   30 days and then break during your demo.

---

## Step 3 — Turn on phone sign-in

1. **Build** → **Authentication** → **Get started**
2. **Sign-in method** tab → **Phone** → enable → Save
3. Still on that page, open **Phone numbers for testing** and add one:

   | Phone number | Verification code |
   |---|---|
   | `+91 9999999999` | `123456` |

   This is worth ninety seconds of your time. It lets you sign in during
   development and on stage without waiting for an SMS, and without
   burning your daily quota. It works only for the number you list.

**Free tier limit: 10 SMS per day.** Real OTPs during testing will exhaust
that fast. Use the test number for everything except one live
demonstration.

---

## Step 4 — Get the backend key

1. Gear icon (top left) → **Project settings** → **Service accounts** tab
2. **Generate new private key** → Generate key
3. A JSON file downloads. Move it to your project root and rename it:

   ```
   fasal-kavach/service-account.json
   ```

**This file is a password.** Anyone holding it has full read and write
access to your database, and it bypasses `firestore.rules` entirely.

Confirm it is ignored before you push:

```bash
git check-ignore -v service-account.json
```

That must print a line naming `.gitignore`. If it prints nothing, **stop
and fix `.gitignore` before committing anything.**

---

## Step 5 — Get the frontend config

1. **Project settings** → **General** tab
2. Scroll to **Your apps** → click the web icon `</>`
3. Nickname: `fasal-kavach-web`. Do **not** tick Firebase Hosting.
4. Copy the `firebaseConfig` values it shows you.

Those six values go in `web/.env.local`. They are public — they ship to
every browser that loads your site, and that is fine. They identify the
project; they do not authorise anything.

---

## Step 6 — Fill in the env files

```bash
cd fasal-kavach

# Backend
cp .env.example .env
# edit .env: GOOGLE_APPLICATION_CREDENTIALS=./service-account.json

# Frontend
cp .env.example web/.env.local
# edit web/.env.local: paste the six NEXT_PUBLIC_FIREBASE_* values
```

---

## Step 7 — Deploy the security rules

```bash
npm install -g firebase-tools
firebase login
firebase deploy --only firestore:rules --project fasal-kavach
```

Until you run this, the rules file in your repo is just a text file. It
does nothing to your live database.

---

## Verify it actually worked

Start the backend:

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

Then check:

```bash
curl http://localhost:8080/internal/status
```

**What you want to see:**

```json
{"backend": "firestore", "persistent": true, "farms_stored": 0, ...}
```

**If it says `"backend": "memory"`** — Firestore did not connect. Your data
will vanish on restart. Look at the startup log; `db.py` prints the exact
reason. Usually one of:

- `.env` not loaded — are you running from inside `api/`?
- Wrong path in `GOOGLE_APPLICATION_CREDENTIALS`
- Firestore database not created yet (Step 2)

Now seed and confirm it persisted:

```bash
curl -X POST http://localhost:8080/internal/seed
# {"status": "seeded", "count": 12, "backend": "firestore"}
```

Open the Firebase console → Firestore Database. **You should see twelve
documents in the `farms` collection.** If they are there, persistence is
real.

Last check — the one that proves the original bug is dead:

```bash
# Stop the server with Ctrl-C. Start it again.
curl http://localhost:8080/internal/status
# farms_stored should still be 12
```

Before this fix, that number was 0.

---

## Run the pipeline

```bash
curl -X POST http://localhost:8080/internal/ingest
```

This fetches live weather from Open-Meteo for all four grid cells, runs
the rules engine over the twelve seeded farms, and writes advisories.

Watch `advisories_generated` and `template_fallbacks` in the response. If
`template_fallbacks` is high, your `GEMINI_API_KEY` is missing or rate
limited — the app still works, which is the whole point of the fallback
ladder, but you should know which path your demo is running on.

---

## Free tier: what you actually have

| | Free per day | Your demo will use |
|---|---|---|
| Firestore reads | 50,000 | roughly 500 |
| Firestore writes | 20,000 | roughly 200 |
| Phone auth SMS | 10 | 1, if you use the test number |
| Cloud Run | 2M requests/month | negligible |

The only limit you can realistically hit is SMS. Use the test number.

---

## The one thing to check before you present

```bash
curl https://<your-deployed-url>/internal/status
```

If it does not say `"backend": "firestore"`, you are demoing on memory and
a scale-to-zero event mid-presentation will empty the app. Check this
after every redeploy.
