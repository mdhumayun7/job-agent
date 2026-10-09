"""
Amazon (amazon.jobs) adapter.

amazon.jobs renders its search results from a public, unauthenticated JSON
endpoint (no login, no cookies):
  https://www.amazon.jobs/en/search.json?normalized_country_code[]=IND&result_limit=100&offset=N&sort=recent

Amazon has tens of thousands of postings worldwide, so this adapter is
scoped to India (country code IND) and capped at MAX_JOBS per run.
It is Amazon-specific (field names are Amazon's own), not a generic adapter.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED  # noqa: E402
from _http import request_json  # noqa: E402

API_URL = "https://www.amazon.jobs/en/search.json"
PAGE_SIZE = 100
MAX_JOBS = 600


def _parse_date(text):
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def map_job(raw: dict, company_display_name: str) -> dict:
    path = raw.get("job_path") or ""
    url = f"https://www.amazon.jobs{path}" if path.startswith("/") else (path or "")
    parts = [raw.get("description") or ""]
    if raw.get("basic_qualifications"):
        parts.append("BASIC QUALIFICATIONS\n" + raw["basic_qualifications"])
    if raw.get("preferred_qualifications"):
        parts.append("PREFERRED QUALIFICATIONS\n" + raw["preferred_qualifications"])
    schedule = (raw.get("job_schedule_type") or "").replace("-", " ").title() or NOT_SPECIFIED
    return Job(
        company=company_display_name,
        job_title=raw.get("title") or NOT_SPECIFIED,
        job_id=str(raw.get("id_icims") or raw.get("id") or "") or None,
        job_url=url,
        apply_url=url,
        location_raw=raw.get("normalized_location") or raw.get("location") or NOT_SPECIFIED,
        city=raw.get("city") or None,
        country=raw.get("country_code") or None,
        employment_type=schedule,
        technology_domain=raw.get("job_category") or NOT_SPECIFIED,
        date_posted=_parse_date(raw.get("posted_date")),
        last_updated=raw.get("updated_time") or None,
        job_description="\n\n".join(p for p in parts if p),
        source_website="amazon.jobs",
        source_type="amazon_jobs_api",
        scraped_at=datetime.now(timezone.utc).isoformat(),
    ).to_dict()


def fetch_amazon_jobs(company_display_name: str = "Amazon", country_code: str = "IND",
                      max_jobs: int = MAX_JOBS) -> list:
    jobs, offset, hits = [], 0, None
    while offset < max_jobs:
        data = request_json(API_URL, tag="amazon", params={
            "normalized_country_code[]": country_code,
            "result_limit": PAGE_SIZE, "offset": offset, "sort": "recent",
        })
        if data is None:
            raise RuntimeError("amazon.jobs search endpoint returned 404 -- endpoint may have moved")
        batch = data.get("jobs") or []
        if hits is None:
            hits = data.get("hits") or 0
        jobs.extend(map_job(r, company_display_name) for r in batch)
        offset += PAGE_SIZE
        if not batch or offset >= hits:
            break
        time.sleep(0.5)
    print(f"[amazon] {company_display_name}: {len(jobs)} jobs fetched (country={country_code}, total available={hits})")
    return jobs


def selftest():
    sample = {"id_icims": "3091234", "title": "SDE I", "normalized_location": "Bengaluru, KA, IND",
              "posted_date": "October 7, 2026", "job_path": "/en/jobs/3091234/sde-i",
              "description": "Build services.", "basic_qualifications": "- Bachelor's in CS",
              "job_schedule_type": "full-time", "job_category": "Software Development"}
    j = map_job(sample, "Amazon")
    assert j["job_url"] == "https://www.amazon.jobs/en/jobs/3091234/sde-i"
    assert j["date_posted"] == "2026-10-07"
    assert j["employment_type"] == "Full Time"
    assert "BASIC QUALIFICATIONS" in j["job_description"]
    assert _parse_date("not a date") is None
    print("adapter_amazon self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        res = fetch_amazon_jobs()
        print(f"Fetched {len(res)} jobs")
        if res:
            print(res[0]["job_title"], "-", res[0]["location_raw"])
