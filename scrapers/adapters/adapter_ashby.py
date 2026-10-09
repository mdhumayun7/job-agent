"""
Ashby ATS adapter.

Uses Ashby's PUBLIC job posting API -- documented, no auth.
Docs: https://developers.ashbyhq.com/docs/public-job-posting-api
Endpoint: https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED, NOT_DISCLOSED  # noqa: E402
from _http import request_json  # noqa: E402

API_BASE = "https://api.ashbyhq.com/posting-api/job-board"

EMPLOYMENT_TYPES = {
    "FullTime": "Full-time", "PartTime": "Part-time", "Intern": "Internship",
    "Contract": "Contract", "Temporary": "Temporary",
}


def map_job(raw: dict, board: str, company_display_name: str) -> dict:
    location = raw.get("location") or NOT_SPECIFIED
    secondary = [s.get("location") for s in (raw.get("secondaryLocations") or []) if s.get("location")]
    if secondary:
        location = "; ".join([location] + secondary)
    comp = raw.get("compensation") or {}
    salary_raw = comp.get("compensationTierSummary") or NOT_DISCLOSED
    work_mode = "Remote" if raw.get("isRemote") else (raw.get("workplaceType") or NOT_SPECIFIED)
    return Job(
        company=company_display_name,
        job_title=raw.get("title") or NOT_SPECIFIED,
        job_id=str(raw.get("id")) if raw.get("id") else None,
        job_url=raw.get("jobUrl", ""),
        apply_url=raw.get("applyUrl") or raw.get("jobUrl", ""),
        location_raw=location,
        work_mode=work_mode,
        employment_type=EMPLOYMENT_TYPES.get(raw.get("employmentType"), raw.get("employmentType") or NOT_SPECIFIED),
        technology_domain=raw.get("department") or raw.get("team") or NOT_SPECIFIED,
        date_posted=raw.get("publishedAt"),
        salary_raw=salary_raw,
        job_description=raw.get("descriptionPlain") or raw.get("descriptionHtml") or "",
        source_website=f"jobs.ashbyhq.com/{board}",
        source_type="ashby_api",
        scraped_at=datetime.now(timezone.utc).isoformat(),
    ).to_dict()


def fetch_ashby_jobs(board: str, company_display_name: str) -> list:
    data = request_json(f"{API_BASE}/{board}", params={"includeCompensation": "true"}, tag="ashby")
    if data is None:
        print(f"[ashby] '{board}' is not a valid Ashby job board (404).")
        return []
    jobs = [map_job(r, board, company_display_name) for r in data.get("jobs", []) if r.get("isListed", True)]
    print(f"[ashby] {company_display_name}: {len(jobs)} jobs fetched")
    return jobs


def selftest():
    sample = {"id": "a1", "title": "Software Engineer, Infra", "location": "Bengaluru",
              "secondaryLocations": [{"location": "Remote - India"}], "isRemote": False,
              "employmentType": "FullTime", "department": "Engineering",
              "publishedAt": "2026-10-01T10:00:00Z", "jobUrl": "https://jobs.ashbyhq.com/x/a1",
              "descriptionPlain": "Build things."}
    j = map_job(sample, "x", "X")
    assert j["employment_type"] == "Full-time"
    assert j["location_raw"] == "Bengaluru; Remote - India"
    assert j["salary_raw"] == NOT_DISCLOSED
    assert j["apply_url"] == "https://jobs.ashbyhq.com/x/a1"
    print("adapter_ashby self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        b = sys.argv[1] if len(sys.argv) > 1 else "openai"
        res = fetch_ashby_jobs(b, sys.argv[2] if len(sys.argv) > 2 else b)
        print(f"Fetched {len(res)} jobs")
