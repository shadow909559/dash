# Key Rotation Checklist — September 21, 2026

> **Context:** Key material for several services was found in git history
> (`apps/desktop/.env`, `.env.production`). The local branches have since
> been purged (see `decisions.md` #140), but **purging history does not
> un-leak values.** Rotation below is the durable fix and stays mandatory.
> Values were never printed into reports; only key names are recorded.

## What was exposed, and where

| Key | Where it lived | Public exposure | Severity | Rotate? |
|---|---|---|---|---|
| `VITE_GEMINI_KEY` | `apps/desktop/.env` @ `b6187a02` (2026-09-05) | Never pushed — local history only, now destroyed | High | **YES (urgent)** |
| `VITE_GROQ_KEY` | same | Never pushed — local history only, now destroyed | High | **YES (urgent)** |
| `VITE_GROK_KEY` | same | Never pushed — local history only, now destroyed | High | **YES (urgent)** |
| `DASH_OPENAI_API_KEY` | `.env.production` @ `e1985fa6` (2026-07-28) | **LIVE on the public repo** (`release-v1` branch; contents API returned 200) | Critical | **YES (now)** |
| `DASH_JWT_SECRET_KEY` | `.env.production` (same commit) | **LIVE on the public repo** (value looks placeholder-ish — treat as exposed anyway) | High | **YES** |
| `DASH_DATABASE_URL`, `DASH_REDIS_URL` | `.env.production` (same commit) | **LIVE on the public repo** — connection strings may embed credentials | Critical if credentials embedded | **Inspect + rotate** |

Why rotate the never-pushed ones at all: the desktop keys sat in a tracked
file for ~2.5 weeks on three branches; rotation is the only durable fix
and costs minutes.

## Rotation steps

### 1. OpenAI (`DASH_OPENAI_API_KEY`) — do first, it is publicly retrievable
1. Sign in at platform.openai.com → API keys.
2. **Revoke** the exposed key immediately.
3. Create a new key; store it in a secret manager or local untracked `.env`.
4. Update every consumer (backend env, deployed hosts) with the new value.
5. Old-key history check: review usage on the OpenAI dashboard for the
   exposure window (2026-07-28 → rotation day) for anomalous spend.

### 2. Gemini (`VITE_GEMINI_KEY`)
1. aistudio.google.com → Get API key → delete the exposed key.
2. Create a replacement; restrict it to the intended APIs where possible.
3. Update consumers.

### 3. Groq (`VITE_GROQ_KEY`)
1. console.groq.com → API Keys → revoke the exposed key.
2. Issue a new one; update consumers.

### 4. xAI Grok (`VITE_GROK_KEY`)
1. console.x.ai → API Keys → revoke, reissue, update consumers.

### 5. `DASH_JWT_SECRET_KEY`
1. Generate a fresh key:
   `python -c "import secrets; print(secrets.token_urlsafe(64))"`
2. Deploy alongside the old one (dual-accept) or accept one forced
   re-login for all sessions when you swap it.
3. Swap, drop the old key, confirm issued-before-swap tokens are rejected.

### 6. `DASH_DATABASE_URL` / `DASH_REDIS_URL`
1. Read the URLs and check whether they embed username/password.
2. If yes: rotate the DB/Redis credentials (managed-console user rotate or
   `ALTER USER ... PASSWORD`), update the URLs in the secret store.
3. If the URLs were placeholder/local (localhost, no creds): no rotation
   needed — record that finding here.

## Local work completed on 2026-09-21 (see decisions.md #140)

- `apps/desktop/.env` and `.env.production` removed from **all local
  branch/tag/stash/checkpoint histories** (two filter-branch passes,
  tips verified byte-identical, `.env.example` templates preserved).
- Reflogs expired, `refs/original` backups deleted, `git gc --prune=now`
  run to completion: the secret **blobs themselves are physically gone**
  from the local object store (verified per-OID with `git cat-file -e`).
- The user's Aug 24 stash was rebuilt without the `.env.production` file;
  its WIP content is intact and `stash pop` works.
- Stale remote-tracking refs that pinned the old objects
  (`origin/heads/release-v1`, `origin/heads/backend-clean`) were deleted
  locally.

## User-side follow-ups (cannot be done from here)

1. **Rotate the keys above** — the OpenAI key first (it is on the public
   repo right now).
2. **Delete the `release-v1` branch on GitHub** (or re-push a cleaned
   replacement). Until then the public repo serves `.env.production`.
3. Optional: contact GitHub Support to purge cached commits/views of the
   removed data, and consider rotating any other credentials that ever
   appeared in tracked env files.
4. Optional hardening: add a CI secret-scanning step; local hooks
   (e.g. pre-commit secret scan) to stop env files from ever being
   `git add`-ed again.
