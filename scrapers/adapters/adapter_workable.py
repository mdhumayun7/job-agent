"""
Workable ATS adapter.

Uses Workable's public job widget API (the same JSON that powers the
embeddable careers widget) -- no auth.
Endpoint: https://apply.workable.com/api/v1/widget/accounts/{account}?details=true
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED  # noqa: E402
from _http import request_json  # noqa: E402

API_BASE = "https://apply.workable.com/api/v1/widget/accounts"


def map_job(raw: dict, account: str, company_display_name: str) -> dict:
    loc_parts = [raw.get("city"), raw.get("state"), raw.get("country")]
    location = ", ".join(p for p in loc_parts if p) or NOT_SPECIFIED
    url = raw.get("url") or raw.get("shortlink") or ""
    return Job(
        company=company_display_name,
        job_title=raw.get("title") or NOT_SPECIFIED,
        job_id=raw.get("shortcode") or raw.get("code"),
        job_url=url,
        apply_url=raw.get("application_url") or url,
        location_raw=location,
        work_mode="Remote" if raw.get("telecommuting") else NOT_SPECIFIED,
        employment_type=raw.get("employment_type") or NOT_SPECIFIED,
        technology_domain=raw.get("department") or raw.get("function") or NOT_SPECIFIED,
        date_posted=raw.get("published_on") or raw.get("created_at"),
        experience_raw=raw.get("experience") or NOT_SPECIFIED,
        job_description=raw.get("description") or "",
        source_website=f"apply.workable.com/{account}",
        source_type="workable_api",
        scraped_at=datetime.now(timezone.utc).isoformat(),
    ).to_dict()


def fetch_workable_jobs(account: str, company_display_name: str) -> list:
    data = request_json(f"{API_BASE}/{account}", params={"details": "true"}, tag="workable")
    if data is None:
        print(f"[workable] '{account}' is not a valid Workable account (404).")
        return []
    jobs = [map_job(r, account, company_display_name) for r in data.get("jobs", [])]
    print(f"[workable] {company_display_name}: {len(jobs)} jobs fetched")
    return jobs


def selftest():
    sample = {"title": "ML Engineer", "shortcode": "ABC123", "city": "Paris", "country": "France",
              "telecommuting": True, "employment_type": "Full-time",
              "url": "https://apply.workable.com/j/ABC123", "published_on": "2026-09-30"}
    j = map_job(sample, "huggingface", "Hugging Face")
    assert j["location_raw"] == "Paris, France"
    assert j["work_mode"] == "Remote"
    assert j["job_id"] == "ABC123"
    print("adapter_workable self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        a = sys.argv[1] if len(sys.argv) > 1 else "huggingface"
        res = fetch_workable_jobs(a, sys.argv[2] if len(sys.argv) > 2 else a)
        print(f"Fetched {len(res)} jobs")
