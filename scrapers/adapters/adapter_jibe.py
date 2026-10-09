"""
iCIMS "Jibe" career-site adapter (AMD, GitHub, ...).

Jibe-hosted sites (careers-home/jobs pages) are backed by a public JSON API:
  GET https://{host}/api/jobs?location=India&page=N&sortBy=relevance&descending=false&internal=false

verified_slug format: "{host}" or "{host}|{location}" (empty location = all).
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED  # noqa: E402
from _http import request_json  # noqa: E402

MAX_PAGES = 40


def map_job(d: dict, host: str, company_display_name: str) -> dict:
    slug = d.get("slug") or d.get("req_id")
    url = f"https://{host}/careers-home/jobs/{slug}?lang=en-us" if slug else (d.get("apply_url") or "")
    desc = "\n\n".join(x for x in (d.get("description"), d.get("qualifications"), d.get("responsibilities")) if x)
    cats = d.get("categories") or []
    domain = cats[0].get("name") if cats and isinstance(cats[0], dict) else NOT_SPECIFIED
    return Job(
        company=company_display_name,
        job_title=d.get("title") or NOT_SPECIFIED,
        job_id=str(d.get("req_id") or slug or "") or None,
        job_url=url,
        apply_url=d.get("apply_url") or url,
        location_raw=d.get("location_name") or d.get("full_location") or NOT_SPECIFIED,
        city=d.get("city"), state_region=d.get("state"), country=d.get("country"),
        work_mode=d.get("location_type") or NOT_SPECIFIED,
        employment_type=d.get("employment_type") or NOT_SPECIFIED,
        technology_domain=domain or NOT_SPECIFIED,
        date_posted=d.get("posted_date") or d.get("create_date"),
        last_updated=d.get("update_date"),
        job_description=desc,
        source_website=host,
        source_type="jibe_api",
        scraped_at=datetime.now(timezone.utc).isoformat(),
    ).to_dict()


def fetch_jibe_jobs(slug: str, company_display_name: str) -> list:
    host, _, location = slug.partition("|")
    tag = f"jibe:{host}"
    jobs, page, total = [], 1, None
    while page <= MAX_PAGES:
        params = {"page": page, "sortBy": "relevance", "descending": "false", "internal": "false"}
        if location:
            params["location"] = location
        data = request_json(f"https://{host}/api/jobs", tag=tag, params=params)
        if data is None:
            print(f"[{tag}] api not found (404)")
            return []
        batch = data.get("jobs") or []
        if total is None:
            total = data.get("totalCount") or data.get("count") or 0
        jobs.extend(map_job(j.get("data") or j, host, company_display_name) for j in batch)
        if not batch or len(jobs) >= total:
            break
        page += 1
        time.sleep(0.3)
    print(f"[{tag}] {company_display_name}: {len(jobs)} jobs fetched (location={location or 'all'}, total={total})")
    return jobs


if __name__ == "__main__":
    print(len(fetch_jibe_jobs(sys.argv[1], sys.argv[2])))
