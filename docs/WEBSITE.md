# Website: government and company jobs portal

The site in `site/` is a static single-page app published to GitHub Pages by the daily workflow. It works in two modes:

- **Without Supabase (default):** everything runs. Profiles, saved jobs, saved searches, reminders and the dashboard are stored in the visitor's browser. Accounts, email alerts and the admin dashboard are hidden.
- **With Supabase:** visitors can create accounts and their data syncs across devices. Editors and admins can manage government records from `#/admin`, and opted-in users get email alerts.

## What is on the site

| Area | Route | Notes |
|---|---|---|
| Home | `#/` | Closing soon, recently added, categories, your matches |
| Government jobs | `#/govt` | Filters for category, status, qualification, state, age, deadline, employment type, fresher, marks, match and verification. Every filter is reflected in the URL |
| Job details | `#/govt/<id>` | Dates, eligibility, posts, fee, selection, interactive eligibility checklist, official links, verification status and last-checked date, report a problem |
| Company jobs | `#/jobs` | CSE / IT openings from company career sites, ranked against your skills |
| Compare | `#/compare` | Up to four recruitments side by side, differences highlighted |
| Deadlines | `#/timeline` | Application, fee, correction and exam dates on one timeline |
| Career explorer | `#/explorer` | Common routes per qualification and current listings whose education rule you meet |
| Profile | `#/profile` | Resume upload (PDF, DOCX, TXT up to 5 MB, read in the browser and never uploaded), review and edit, optional personal details |
| Dashboard | `#/dashboard` | Saved jobs, saved searches, recently viewed, reminder settings, configurable sections, delete all data |
| Notifications | `#/notifications` | Deadline reminders, changed dates, new matches, saved-search hits |
| Admin | `#/admin` | Editors and admins only: records, editor with validation, publish and archive, reports, link checks, audit history |
| Static pages | `/govt/`, `/govt/<id>/` | Crawlable summaries with meta tags and structured data, listed in `sitemap.xml` |

Keyboard: `Ctrl+K` or `/` opens the command center, `g` then a letter jumps to a section, `?` lists shortcuts, `Alt+G` opens the guide. The guide can be turned off and respects reduced-motion settings.

## Eligibility labels

The checklist compares the visitor's profile with the conditions recorded for a notice and shows one of: **Strong match**, **Possible match**, **More information required**, or **Does not match your profile**. These are estimates. Equivalent qualifications, special relaxations, physical standards and documents are decided by the recruiting body, and the site says so wherever a label appears.

## Government data

Records live in `data/govt_jobs.json` (reviewed seed) and, once Supabase is set up, in the `govt_jobs` table. Every record must point to an official source and carries a verification state:

- `verified`: an editor read the official notice; `checked_on` is shown on the listing.
- `awaiting`: collected automatically from an official page (ISRO, C-DAC). Title, dates and link only.
- `revised`: the notice was corrected after the record was checked.

Never copy data from other job portals. When a value is not in the notice, leave it `null`; the site shows "Not recorded".

To add or change a record without Supabase, edit `data/govt_jobs.json`, then run:

```bash
python scripts/validate_govt_jobs.py   # schema, dates, duplicates
python scripts/make_seed_sql.py        # keeps supabase/seed.sql in sync (CI checks this)
```

## Setting up Supabase

1. Create a project at supabase.com (the free tier is enough).
2. In the SQL editor, run `supabase/migrations/20261011000000_init.sql`, then `supabase/seed.sql`. Or with the Supabase CLI: `supabase link` then `supabase db push`, and run the seed file.
3. Authentication > URL configuration: set the Site URL to `https://<user>.github.io/job-agent/site/` and add the same URL to the redirect allow list. Email confirmation should stay on.
4. Sign up on the website with your own email, then make yourself admin in the SQL editor:

   ```sql
   update public.profiles set role = 'admin'
   where id = (select id from auth.users where email = 'you@example.com');
   ```

   After that, admins can promote editors with `select public.set_user_role('<user uuid>', 'editor');`.
5. Add GitHub settings (Settings > Secrets and variables > Actions):

   | Name | Kind | Value |
   |---|---|---|
   | `SUPABASE_URL` | Variable | `https://<project>.supabase.co` |
   | `SUPABASE_ANON_KEY` | Variable | Project Settings > API > anon public key |
   | `SUPABASE_SERVICE_ROLE_KEY` | Secret | Project Settings > API > service_role key. Never put this in a variable or in the site |
   | `SITE_URL` | Variable (optional) | Defaults to `https://mdhumayun7.github.io/job-agent` |
   | `EMAIL_ID`, `EMAIL_PASSWORD` | Secret | Gmail address and app password, already used by the daily digest; also used for user alerts |

The anon key is public by design: every table has row level security (users only see their own rows, the public only sees published records, only staff can edit, only admins can delete, and every change to a record is written to the audit log). `tests/sql/run_rls_tests.sh` checks these rules against a local PostgreSQL 16.

## What the daily workflow does for the site

1. Builds company job data from the ATS pipeline.
2. Validates the government seed, then `scripts/build_govt_data.py` merges reviewed records with automated official notices. With Supabase, automated notices are inserted as unpublished drafts for an editor and only published rows are shown.
3. `scripts/build_site.py` copies the app, writes `site/js/config.js` from the variables, and generates the static SEO pages, `sitemap.xml`, `robots.txt` and `404.html`.
4. Deploys to GitHub Pages.
5. On the 09:00 IST run only: `scripts/check_links.py` checks every official link (results in the admin dashboard), and `scripts/send_user_alerts.py` emails opted-in users. Each alert item is recorded in `email_log`, so it is never sent twice.

## Launch checklist

1. Settings > Pages > Build and deployment > Source: **GitHub Actions**.
2. Optional: set up Supabase as above. Without it the site works in device-storage mode.
3. Run the workflow once from the Actions tab (Daily Job Search > Run workflow) and open `https://<user>.github.io/job-agent/site/`.
4. Submit `https://<user>.github.io/job-agent/sitemap.xml` in Google Search Console. On a project Pages site, crawlers only read `robots.txt` at the domain root, so the sitemap has to be submitted by hand (with a custom domain it is picked up automatically).
5. Review new automated notices in `#/admin` each week and keep reviewed records current; the site shows how long ago each record was checked.

## Running locally

```bash
python tests/e2e/make_fixture.py        # fake company jobs, for local testing only
python scripts/build_govt_data.py       # government data from the seed file
python -m http.server 8811              # from the repository root
# open http://127.0.0.1:8811/site/index.html
```

Tests:

```bash
npm test                                # eligibility engine and resume parser
sudo bash tests/sql/run_rls_tests.sh    # database rules (needs PostgreSQL 16)
BASE=http://127.0.0.1:8811/site/index.html python tests/e2e/test_site.py
```

Set `E2E_CDN=1` to include the PDF and DOCX parsing checks, which load pdf.js and mammoth from cdnjs. The Tests workflow runs all of the above on every push.

## Known limitations

- Government coverage is small: 8 reviewed records (SSC and Indian Coast Guard) plus automated ISRO and C-DAC notices. UPSC, IBPS, railway boards and state commissions need records added from their official notices.
- Eligibility labels are estimates based on the recorded conditions, never a decision.
- Resume parsing is rule-based and works best on text-based PDFs; scanned PDFs have no text to read. Everything it extracts is shown for review before saving.
- Accounts, cross-device sync, admin editing and email alerts need Supabase.
- Some company career sites (for example TCS) block automated access and are not included.
