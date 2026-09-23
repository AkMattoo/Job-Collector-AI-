# Job Radar

A job-search agent with no server. A daily Python pipeline pulls data roles from company job boards,
filters them with cheap rules, scores the survivors against my resume with Gemini, and publishes the
results. A static site shows them, with a chat agent and a "try it with your resume" feature.

```
GitHub Actions (daily)                     Vercel (free)
┌──────────────────────────────┐           ┌──────────────────────────────┐
│ fetch  Greenhouse/Lever/Ashby│           │ index.html  table + chat UI  │
│ normalize → one schema       │  commit   │ /data/jobs.json  (static)    │
│ filter  title/location/age   │ ────────▶ │ /api/chat   agent + tool     │
│ score   Gemini, batched      │  push     │ /api/match  resume rescoring │
│ store   data/scored.json     │           └──────────────────────────────┘
└──────────────────────────────┘
```

**Design decisions worth knowing**
- *Filter before you spend.* Deterministic rules drop most postings before any model call.
- *At-least-once.* A job is written to the store only after it's scored. If Gemini fails, the job is retried next run instead of being silently lost.
- *Measured signals, not guesses.* `days_live`, `still_open` and `open_roles_at_company` come from the boards. The model is told to return blank pay rather than estimate, and never rates culture.
- *Structured output.* Gemini is called with a JSON response schema, and replies are still validated before use.

## Setup (about 20 minutes, all free)

**1. Put it on GitHub.** Create a new **public** repository (public repos get free Actions minutes), then upload
this folder's contents. Easiest: on the empty repo page click **uploading an existing file** and drag everything in,
including the hidden `.github` folder. (Or use `git push` if you're comfortable with it.)

**2. Add secrets to GitHub.** Repo → **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Needed for | Where to get it |
|---|---|---|
| `GEMINI_API_KEY` | scoring | aistudio.google.com/apikey |
| `ADZUNA_APP_ID` | job search | developer.adzuna.com (free, no card) |
| `ADZUNA_APP_KEY` | job search | same page |
| `APIFY_TOKEN` | LinkedIn search (optional) | apify.com → Settings → Integrations |

And one **variable** (the Variables tab, not Secrets): `APIFY_ACTOR`, e.g. `bebity~linkedin-jobs-scraper`.
Leave the Apify ones out and the run simply skips LinkedIn.

**3. Run the collector once.** Repo → **Actions** tab → enable workflows if asked → **Collect jobs** → **Run workflow**.
It takes a few minutes. When it's green, `public/data/jobs.json` will have been updated by a commit from `job-agent-bot`.
After that it runs by itself every day at 14:00 UTC.

**4. Deploy the site on Vercel.** Sign in to vercel.com with GitHub → **Add New → Project** → import the repo →
leave the framework as **Other** → under **Environment Variables** add `GEMINI_API_KEY` again → **Deploy**.
Every time the collector commits new data, Vercel redeploys automatically.

## Everyday changes
- **Your profile**: edit `profile.md` on GitHub. The next run scores new jobs against it.
- **What to search for**: `ROLE_KEYWORDS` and `LOCATIONS` in `collector/config.py`.
- **Pay**: `SALARY_TARGET` ranks jobs at or above it higher. `HARD_SALARY_FLOOR` stays 0 by default
  on purpose — most postings don't state pay, and an unknown salary is not evidence of a low one.
- **Sources**: `USE_ADZUNA`, `USE_LINKEDIN`, `USE_BOARDS` in `collector/config.py`.
  With `USE_BOARDS = True`, the old per-company watchlist in `COMPANIES` runs too.
- **Filters and thresholds**: also in `collector/config.py` (`MAX_AGE_DAYS`, `MIN_SCORE`, keyword lists).
- **Rescore everything** after a big profile change: replace `data/scored.json` with `{}` and rerun the workflow.

## Run it locally
```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q            # 12 tests, no network or key needed
npm test                       # 4 tests for the chat agent and resume matcher
GEMINI_API_KEY=... python -m collector.main
```
On Windows PowerShell: `$env:GEMINI_API_KEY="..."; python -m collector.main`

## Cost and limits
Everything runs on free tiers. Gemini's free tier can't bill you; if a visitor uses up the day's quota,
the chat and resume features show a "quota used up" message until it resets, and the daily collector
retries anything it couldn't score on the next run.
