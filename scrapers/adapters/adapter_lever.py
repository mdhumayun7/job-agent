"""
Lever ATS adapter.

Uses Lever's PUBLIC postings API -- documented, no auth.
Docs: https://github.com/lever/postings-api
Endpoint: https://api.lever.co/v0/postings/{company}?mode=json
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))

import requests
from datetime import datetime, timezone
from job_schema import Job, NOT_SPECIFIED

API_BASE = "https://api.lever.co/v0/postings"
TIMEOUT = 15


def fetch_lever_jobs(company_slug: str, company_display_name: str, max_retries: int = 3) -> list:
    url = f"{API_BASE}/{company_slug}?mode=json"
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers={
                "User-Agent": "job-agent-bot/2.0 (+https://github.com/mdhumayun7/job-agent)"
            })
            if resp.status_code == 404:
                print(f"[lever] '{company_slug}' is not a valid Lever company slug (404). "
                      f"Verify at jobs.lever.co/{company_slug}")
                return []
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            last_error = e
            print(f"[lever] attempt {attempt}/{max_retries} failed for '{company_slug}': {e}")
    else:
        print(f"[lever] giving up on '{company_slug}' after {max_retries} attempts: {last_error}")
        return []

    jobs = []
    for raw in data:
        categories = raw.get("categories", {}) or {}
        job = Job(
            company=company_display_name,
            job_title=raw.get("text", NOT_SPECIFIED),
            job_id=raw.get("id"),
            job_url=raw.get("hostedUrl", ""),
            apply_url=raw.get("applyUrl", raw.get("hostedUrl", "")),
            location_raw=categories.get("location", NOT_SPECIFIED),
            employment_type=categories.get("commitment", NOT_SPECIFIED),
            technology_domain=categories.get("team", NOT_SPECIFIED),
            date_posted=(
                datetime.fromtimestamp(raw["createdAt"] / 1000, tz=timezone.utc).isoformat()
                if raw.get("createdAt") else None
            ),
            job_description=raw.get("descriptionPlain", raw.get("description", "")),
            source_website=f"jobs.lever.co/{company_slug}",
            source_type="lever_api",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
        jobs.append(job.to_dict())

    print(f"[lever] {company_display_name}: {len(jobs)} jobs fetched")
    return jobs


if __name__ == "__main__":
    import sys
    slug = sys.argv[1] if len(sys.argv) > 1 else "netflix"
    name = sys.argv[2] if len(sys.argv) > 2 else slug
    results = fetch_lever_jobs(slug, name)
    print(f"Fetched {len(results)} jobs for {name}")
