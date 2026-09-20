"""
SmartRecruiters ATS adapter.
Docs: https://developers.smartrecruiters.com/docs/job-postings-api
Endpoint: https://api.smartrecruiters.com/v1/companies/{company}/postings
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))

import requests
from datetime import datetime, timezone
from job_schema import Job, NOT_SPECIFIED

API_BASE = "https://api.smartrecruiters.com/v1/companies"
TIMEOUT = 15


def fetch_smartrecruiters_jobs(company_slug: str, company_display_name: str, max_retries: int = 3) -> list:
    url = f"{API_BASE}/{company_slug}/postings"
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=TIMEOUT, headers={
                "User-Agent": "job-agent-bot/2.0 (+https://github.com/mdhumayun7/job-agent)"
            })
            if resp.status_code == 404:
                print(f"[smartrecruiters] '{company_slug}' is not a valid company slug (404).")
                return []
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            last_error = e
            print(f"[smartrecruiters] attempt {attempt}/{max_retries} failed for '{company_slug}': {e}")
    else:
        print(f"[smartrecruiters] giving up on '{company_slug}' after {max_retries} attempts: {last_error}")
        return []

    jobs = []
    for raw in data.get("content", []):
        location = raw.get("location", {}) or {}
        location_str = ", ".join(filter(None, [location.get("city"), location.get("region"), location.get("country")])) or NOT_SPECIFIED

        # Postings list doesn't include full description -- fetch it per-job.
        description = ""
        posting_id = raw.get("id")
        if posting_id:
            try:
                detail_resp = requests.get(f"{API_BASE}/{company_slug}/postings/{posting_id}", timeout=TIMEOUT)
                if detail_resp.status_code == 200:
                    detail = detail_resp.json()
                    sections = (detail.get("jobAd", {}) or {}).get("sections", {}) or {}
                    description = " ".join(
                        (s.get("text", "") or "") for s in sections.values() if isinstance(s, dict)
                    )
            except Exception as e:
                print(f"[smartrecruiters] could not fetch detail for posting {posting_id}: {e}")

        job = Job(
            company=company_display_name,
            job_title=raw.get("name", NOT_SPECIFIED),
            job_id=str(posting_id) if posting_id else None,
            job_url=raw.get("ref", ""),
            apply_url=raw.get("applyUrl", raw.get("ref", "")),
            location_raw=location_str,
            date_posted=raw.get("releasedDate"),
            job_description=description,
            source_website=f"smartrecruiters.com/{company_slug}",
            source_type="smartrecruiters_api",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
        jobs.append(job.to_dict())

    print(f"[smartrecruiters] {company_display_name}: {len(jobs)} jobs fetched")
    return jobs


if __name__ == "__main__":
    import sys as _sys
    slug = _sys.argv[1] if len(_sys.argv) > 1 else "freshworks"
    name = _sys.argv[2] if len(_sys.argv) > 2 else slug
    results = fetch_smartrecruiters_jobs(slug, name)
    print(f"Fetched {len(results)} jobs for {name}")
    if results:
        print(results[0]["job_title"], "-", results[0]["location_raw"])
