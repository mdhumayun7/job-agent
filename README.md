# Job Agent

Automated job-search pipeline for Indian freshers and early-career engineers. It scrapes eleven job boards, scores every listing against your profile, filters out the noise, and emails you a ranked daily digest — either on your own machine or entirely on GitHub Actions.

<p>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="Playwright" src="https://img.shields.io/badge/scraping-Playwright-2ea44f">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-lightgrey">
</p>

---

## Why this exists

Applying as a fresher means checking the same ten portals every morning, re-reading the same irrelevant BPO and telecalling listings, and losing the good openings to a two-day delay. This project turns that routine into a single scheduled job: scrape once a day, rank against your actual skills, drop everything below your threshold, and send the rest to your inbox as a formatted digest.

---
---

## What a full run looks like

| | |
|---|---|
| Sources ingested | 11 job boards + 9 government portals |
| Listings persisted | 2,158 |
| After deduplication and filtering | 793 → 357 ranked matches |
| Noise reduction | 55% |
| Manual triggers required | 0 |

Deduplication uses fuzzy matching (`SequenceMatcher`) at a 0.88 similarity
threshold. That number is the one worth arguing about: lower it and genuinely
different roles start merging, raise it and near-duplicates survive into the
digest. It was set by inspecting the collisions on either side of the boundary,
not by picking something round.

Each scraper retries in isolation, so a portal that breaks overnight degrades
one source instead of producing an empty run — which is the difference between
a pipeline you trust and one you end up checking manually anyway.
---

## Features

| | Feature | Detail |
|---|---|---|
| 🌐 | **11 sources** | Naukri, LinkedIn, Indeed, Wellfound, Unstop, Foundit, Internshala, Shine, TimesJobs, HackerEarth, and 9 government portals (ISRO, DRDO, BARC, BEL, NPCIL, ECIL, NIELIT, C-DAC, HAL) |
| 🎯 | **Match scoring** | Every job scored 0–100 against your skills, target roles, and preferred cities |
| 🧹 | **Smart filters** | Drops expired postings, negative-keyword roles (sales, BPO, telecalling), duplicate companies, and blacklisted employers |
| 🤖 | **Optional LLM enrichment** | Uses a Groq-hosted model to re-score and summarise listings when `GROQ_API_KEY` is set; falls back to the rule-based scorer otherwise — no API key required to run |
| 📧 | **Email digest** | Styled HTML email with your top matches, grouped by platform |
| 📊 | **Streamlit dashboard** | Local UI with charts, filters, and an application tracker |
| 🗃️ | **Persistence** | SQLite for dedupe and history, Excel exports for tracking, HTML daily reports |
| 📄 | **Resume tooling** | Parses your resume (PDF/DOCX) and tailors bullet emphasis per job |
| 🎤 | **Interview prep** | Generates role-specific technical and HR question sheets |
| ⏰ | **Fully automated** | GitHub Actions cron, or a local scheduler / Windows Task Scheduler script |

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/mdhumayun7/job-agent.git
cd job-agent

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env             # Windows: copy .env.example .env
```

Open `.env` and fill in your profile, target keywords, and email credentials. Every value in `config.py` reads from the environment, so `.env` is the only file you ever need to edit. It is git-ignored — **never commit it.**

For Gmail, `EMAIL_PASSWORD` must be a [16-character App Password](https://myaccount.google.com/apppasswords), not your account password.

### 3. Run

```bash
python main.py                              # scrape all sources
python main.py --sites naukri linkedin      # pick specific sources
python main.py --sites all --top 30         # print top 30 matches
python email_alert.py                       # send the digest
```

Results land in `output/jobs_found.json` and `output/jobs_found.xlsx`.

---

## The full pipeline

`main.py` handles scraping only. To run every stage in order:

```bash
python scheduler.py
```

That executes:

| Step | Script | Produces |
|---|---|---|
| 1 | `main.py` | `output/jobs_found.json` |
| 2 | `phase2_enrichment.py` | `output/jobs_enriched.json` |
| 3 | `smart_filters.py` | filtered, deduplicated set |
| 4 | `resume_tailor.py` | `output/tailored_jobs.xlsx` |
| 5 | `interview_prep.py` | `output/interview_prep.xlsx` |
| 6 | `excel_exporter.py` | styled multi-sheet workbook |
| 7 | `report_generator.py` | `output/job_report_YYYYMMDD.html` |
| 8 | `analytics.py` | `output/analytics_summary.json` |

Dashboard:

```bash
streamlit run dashboard.py
```

---

## CLI reference

```
python main.py [--sites SITE ...] [--top N] [--retries N]

  --sites     naukri | linkedin | indeed | angellist | govt | unstop |
              foundit | internshala | shine | timesjobs | hackerearth | all
              (default: all)
  --top       number of top matches printed to console (default: 20)
  --retries   attempts per scraper before giving up (default: 2)
```

---

## Automation with GitHub Actions

The workflow in `.github/workflows/daily.yml` runs every day at **09:00 IST** and can also be triggered manually from the **Actions** tab.

**Setup:** go to *Settings → Secrets and variables → Actions* and add:

| Secret | Required | Purpose |
|---|---|---|
| `EMAIL_ID` | yes | Gmail address that sends the digest |
| `EMAIL_PASSWORD` | yes | Gmail App Password |
| `NOTIFY_EMAIL` | no | Where to deliver (defaults to `EMAIL_ID`) |
| `GROQ_API_KEY` | no | Enables LLM enrichment |
| `APPLICANT_NAME` / `APPLICANT_EMAIL` / `APPLICANT_PHONE` | no | Used by resume and cover-letter tooling |

Search settings (keywords, skills, cities) live as plain `env:` values at the top of the workflow file — edit them there, no secrets needed.

Each run uploads `output/` and `logs/` as a downloadable artifact, kept for 14 days.

**Two things worth knowing:**

- Job portals routinely block datacentre IPs, so a hosted run will usually return fewer listings than a run from your own machine. The workflow treats an empty scrape as a warning, not a failure, and skips the email rather than sending a blank digest.
- GitHub disables scheduled workflows in repositories with no activity for 60 days. Push a commit or hit *Run workflow* occasionally to keep the cron alive.

### Local scheduling instead

```bash
python scheduler.py --interval 6      # every 6 hours
```

On Windows, `setup_scheduler.ps1` registers `run_daily.bat` with Task Scheduler.

---

## Project structure

```
job-agent/
├── main.py                  # scraper orchestrator + CLI
├── config.py                # all settings, loaded from .env
├── scheduler.py             # runs the 8-stage pipeline
├── dashboard.py             # Streamlit UI
│
├── scrapers/                # one module per job board
│   ├── naukri_scraper.py    linkedin_scraper.py    indeed_scraper.py
│   ├── angellist_scraper.py unstop_scraper.py      foundit_scraper.py
│   ├── internshala_scraper.py shine_scraper.py     timesjobs_scraper.py
│   ├── hackerearth_scraper.py govt_scraper.py      company_ratings.py
│
├── phase2_enrichment.py     # LLM / heuristic re-scoring
├── smart_filters.py         # expiry, dedupe, blacklist, salary parsing
├── resume_parser.py         # PDF/DOCX resume extraction
├── resume_tailor.py         # per-job resume emphasis
├── interview_prep.py        # question generation
├── excel_exporter.py        # styled workbooks
├── report_generator.py      # HTML daily report
├── analytics.py             # trends and summary stats
├── email_alert.py           # HTML email digest
├── db.py / history_tracker.py / status_tracker.py
├── auto_apply.py / full_auto_apply.py
│
└── .github/workflows/daily.yml
```

Generated folders (`output/`, `logs/`, `data/`, `browser_data/`) are created at runtime and git-ignored.

---

## Configuration reference

Key `.env` variables:

| Variable | Example | Notes |
|---|---|---|
| `SEARCH_KEYWORDS` | `python developer fresher,ml fresher` | Comma-separated |
| `YOUR_SKILLS` | `python,pandas,flask,sql` | Drives match scoring |
| `NEGATIVE_KEYWORDS` | `sales,bpo,telecalling` | Auto-rejected roles |
| `CITIES` | `Bangalore,Pune,Remote` | Preferred locations |
| `MIN_MATCH_SCORE` | `40` | Discard anything below |
| `MAX_JOBS_PER_SITE` | `50` | Per-source cap |
| `REMOTE_ONLY` | `false` | Remote listings only |
| `HEADLESS` | `true` | Set `false` to watch the browser |
| `REQUEST_DELAY` | `2` | Seconds between requests |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `0 jobs found` from every source | Portal layout changed or IP blocked. Run with `HEADLESS=false` to watch, and try a single source: `python main.py --sites indeed` |
| Playwright timeout | Increase `REQUEST_DELAY`; re-run `python -m playwright install chromium` |
| Email not sending | Confirm `EMAIL_PASSWORD` is an App Password and 2FA is on |
| `ModuleNotFoundError` | Virtualenv not active, or re-run `pip install -r requirements.txt` |
| Actions run is green but no email | Expected when the scrape returned nothing — check the run summary for the warning |

---

## Roadmap

- [ ] Telegram / WhatsApp notifications
- [ ] Company-level deduplication across runs
- [ ] Referral-contact lookup per listing
- [ ] Hosted dashboard

---

## Disclaimer

Built for personal job-search use. Scraping is rate-limited and respects each site's structure, but you are responsible for complying with the terms of service of any portal you point it at. The auto-apply modules are experimental — review anything before it is submitted on your behalf.

## Author

**MD Humayun** — M.Tech CS (Information Security & Privacy), SVNIT Surat
[Portfolio](https://mdhumayun7.github.io/MD-HUMAYUN-PORTFOLIO/) ·
[LinkedIn](https://www.linkedin.com/in/md-humayun-82051521a/)

## License

MIT
