# Free hosting: Vercel + Render + Neon

This guide puts the AI Career Guidance App online at no cost, so you can share one link and collect feedback.

```
Browser ──https──▶ Vercel (website + forwards /api/*) ──https──▶ Render (API container) ──TLS──▶ Neon (PostgreSQL 18)
```

* **Vercel** serves the React website. It also forwards every `/api/...` request to Render, so the browser only
  ever talks to one address. Login cookies and CSRF protection depend on this.
* **Render** (free plan) runs the API container from `backend/Dockerfile` using [`render.yaml`](../../render.yaml).
* **Neon** (free plan) stores all data in PostgreSQL 18. Row-level security works the same as locally.

## What works and what doesn't on the free tiers

| Feature | Free hosting |
|---|---|
| Accounts, profile, skills, evidence, roles, gaps, simulator, knowledge graph, roadmap | Works |
| Readiness estimate | Works. The synthetic-data demo model ships inside the image and is activated automatically. |
| Resume / job-description analysis | Works. The **uploaded file itself** is lost when Render restarts or sleeps; the extracted analysis stays in the database. |
| Feedback (sidebar "Send feedback" button, admin **Feedback** tab) | Works |
| **Personalized Mentor** | **Not available.** Render has no GPU and cannot run Ollama, so the app shows the mentor as offline. |
| **Email** (verification, password reset) | **Not available.** Render's free plan blocks outgoing SMTP. Email verification is switched off, and anyone who forgets their password needs a new account. |

## Measured in a local simulation (2026-10-17 to 2026-10-21)

The real Vercel, Render and Neon accounts could not be tested from here. Instead, the same image ran locally with
Render's free limits (512 MB memory, 0.1 CPU) against a fresh PostgreSQL 18 database set up exactly as below
(non-superuser owner role plus [`infra/neon/setup.sql`](../../infra/neon/setup.sql)):

* The automated smoke journey passed: register, log in, onboard, readiness, skill gaps, roadmap, resume upload,
  feedback, account deletion.
* **First start** on an empty database took **128 s** (migrations, catalogue, model registration, API start).
  **Waking up** later took **110 s**.
* Memory: about **211 MiB** of program memory. The rest of the 512 MiB filled with file cache that the kernel
  reclaims; there were no out-of-memory kills.
* At 0.1 CPU, registering took 6–12 s and logging in 4–6 s, because password hashing is deliberately expensive.

**Not verified:** the real accounts, TLS to Neon (including `channel_binding`), cookie behaviour through Vercel's
forwarding, and the uptime pinger.

---

## Before you start

You need a GitHub account with access to the repository, plus free accounts on [Neon](https://neon.com),
[Render](https://render.com) and [Vercel](https://vercel.com). Sign in to Render and Vercel **with GitHub**.

Generate two secrets on your computer. Run these in PowerShell from the `backend` folder, then keep the output in a
password manager. Never put it in a file in the repository.

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

That is the **app database password**.

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

That is the **FIELD_ENCRYPTION_KEY**. It encrypts users' MFA secrets. If you lose it, users with MFA turned on can no
longer sign in.

Pick your Vercel project name now (for example `ai-career-guidance`). Your site will then be
`https://ai-career-guidance.vercel.app`, unless that name is already taken.

## Step 1 — Neon (database)

1. Create a project. **Postgres version: 18** (the schema needs PostgreSQL 18's `uuidv7()`).
   **Region: AWS Asia Pacific (Singapore)**, the same region as the Render service.
2. Open the **SQL Editor** (database `neondb`). Paste the contents of
   [`infra/neon/setup.sql`](../../infra/neon/setup.sql) and replace `PASTE_GENERATED_PASSWORD_HERE` with the app
   database password. Run it. The final check must show `f` in every column. Don't save the edited SQL anywhere.
3. Open **Connect**. Choose role **neondb_owner** and turn **Connection pooling off**, so the host name has no
   `-pooler`. Copy the connection string. This is your **MIGRATION_DATABASE_URL**.
4. Build your **DATABASE_URL** from that string. Change the user `neondb_owner` to `twinpath_app` and the password
   to the app database password; keep everything else. The generated password contains only URL-safe characters,
   so it needs no escaping.

## Step 2 — Render (API)

1. In the Render dashboard choose **New → Blueprint**, then select this GitHub repository. Render reads
   [`render.yaml`](../../render.yaml) and proposes one free web service, `ai-career-guidance-api`.
2. When it asks for the secret values, enter:
   * `DATABASE_URL` and `MIGRATION_DATABASE_URL` from Step 1.
   * `FIELD_ENCRYPTION_KEY` from "Before you start".
   * `ALLOWED_ORIGINS` and `PUBLIC_APP_URL`: your planned Vercel address, for example
     `https://ai-career-guidance.vercel.app`. Use https, and no trailing slash.

   Render generates `SECRET_KEY` itself.
3. Apply. The first build takes several minutes, and the first start about 2 more.
4. Note the service URL shown at the top of the service page. Open `<service URL>/api/v1/health/ready`. You should
   see `"database": "ok"`, `"readiness_model": "ok"` and `"mentor_llm": "unavailable"`. The overall status reads
   `degraded` only because the mentor is off, which is expected.
5. If the URL is **not** `https://ai-career-guidance-api.onrender.com`, edit the `destination` in
   [`frontend/vercel.json`](../../frontend/vercel.json) to your URL, then commit and push.

## Step 3 — Vercel (website)

1. In Vercel choose **Add New → Project** and import this GitHub repository.
2. Set **Root Directory** to `frontend`. Vercel then picks up `frontend/vercel.json` (Vite build, API forwarding,
   security headers). Name the project as planned and deploy.
3. If your final address differs from the one you gave Render, update `ALLOWED_ORIGINS` and `PUBLIC_APP_URL` in
   Render (**Environment**), then save. Render redeploys by itself.

## Step 4 — Keep the API awake

Free Render services sleep after about 15 minutes without traffic, and waking takes about 2 minutes. Vercel stops
waiting after about 30 seconds, so the first visitor after a quiet spell would see an error.

Create a free monitor (for example on [UptimeRobot](https://uptimerobot.com) or [cron-job.org](https://cron-job.org))
that requests **`<Render service URL>/api/v1/health/live`** every 5–10 minutes.

* Use `/live`, not `/ready`. `/live` doesn't touch the database, so Neon can still pause and save its free compute
  hours.
* One always-on service uses about 744 of Render's 750 free hours a month, so don't add a second free Render
  service.

## Step 5 — Check it and make yourself an admin

From the `backend` folder:

```bash
uv run python scripts/smoke_hosted.py https://ai-career-guidance.vercel.app
```

This walks the main journey with a temporary account and then deletes that account. Every request line should
start with `ok`, and the last line should say the smoke test passed.

To create your administrator account in the hosted database, set the app connection string for the current
PowerShell window only, then run the command. It asks for a new password.

```powershell
$env:DATABASE_URL = "<your DATABASE_URL from Step 1>"; uv run python -m app.cli create-admin you@example.com; Remove-Item Env:DATABASE_URL
```

## Step 6 — Share the link and read feedback

* Share `https://<your project>.vercel.app`. People register, use the app, and press **Send feedback** in the
  sidebar (or in the menu on phones).
* Sign in as the admin and open **Administration → Feedback**. Ratings and comments appear there, newest first,
  refreshed every 30 seconds, without names or emails.
* You can also query Neon directly in its SQL Editor:

  ```sql
  SELECT created_at, target_type, target_id, rating, comment
  FROM user_feedback ORDER BY created_at DESC LIMIT 100;
  ```

## Backups (do this — Neon's free plan only keeps 6 hours of history)

Run regularly from any folder that is **not** inside the repository. This needs Docker; the dump contains personal
data, so store it privately.

```powershell
docker run --rm -v "${PWD}:/backup" postgres:18.6-alpine pg_dump "<your MIGRATION_DATABASE_URL>" -Fc -f /backup/ai-career-guidance.dump
```

To restore into an empty Neon database:

1. Run `setup.sql` first.
2. Run `pg_restore --no-owner --no-privileges` with the owner connection string.
3. Re-run the `GRANT` and `REVOKE` lines from [`infra/postgres/grants.sql`](../../infra/postgres/grants.sql), with
   `twinpath_owner` replaced by `neondb_owner`.

The restore path on Neon is **not verified**; test it once before you rely on it.

## Updating and rolling back

* Pushing to `main` redeploys both services automatically. Migrations run when the API starts.
* **Rollback:** use Render's **Rollback** on the previous deploy, and in Vercel promote the previous deployment.
  If a release changed the database schema, take a backup before deploying, because rolling back code doesn't undo
  a migration.

## Security notes for this setup

* Vercel and Render provide HTTPS automatically, and Neon requires TLS.
* The API runs with `TWINPATH_ENV=production`. It refuses to start with unsafe settings (http origins, insecure
  cookies, placeholder passwords).
* The API connects as `twinpath_app`, which cannot bypass row-level security.
* The Render URL is publicly reachable. Every endpoint still requires authentication, CSRF protection and the
  allowed Origin. However, someone calling Render directly can fake their IP address, and so get around the
  per-IP rate limits. Per-account limits and lockouts still apply.
* Free tiers come with no uptime guarantee. Vercel's free Hobby plan is for personal, non-commercial use, so check
  that this fits how you use it.
* The readiness model is a demonstration trained on synthetic data. Tell your testers so, which the app also does.
