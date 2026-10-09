"""
Eightfold career-site adapter (Microsoft, Qualcomm, Ericsson, Infineon, ...).

Eightfold-hosted career sites render from a public JSON API that the page
itself calls, no login needed:
  search: GET https://{host}/api/pcsx/search?domain={domain}&query=&location=India&start=N
  detail: GET https://{host}/api/pcsx/position_details?position_id={id}&domain={domain}&hl=en

verified_slug format: "{host}|{domain}"  e.g. "apply.careers.microsoft.com|microsoft.com"
Scoped to India. Descriptions are fetched only for CSE-relevant titles.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED  # noqa: E402
from _http import request_json  # noqa: E402
from adapter_workday import _is_cse_title  # noqa: E402

PAGE = 10           # Eightfold returns 10 per page
MAX_JOBS = 400
DETAIL_CAP = 40


def _ts_to_date(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError):
        return None


def fetch_eightfold_jobs(slug: str, company_display_name: str, location: str = "India",
                         max_jobs: int = MAX_JOBS, detail_cap: int = DETAIL_CAP) -> list:
    host, domain = slug.split("|")
    tag = f"eightfold:{domain}"
    base = f"https://{host}/api/pcsx"
    positions, start, total = [], 0, None
    while start < max_jobs:
        data = request_json(f"{base}/search", tag=tag, max_retries=5,
                            params={"domain": domain, "query": "", "location": location, "start": start})
        if data is None:
            print(f"[{tag}] search endpoint not found (404)")
            return []
        d = data.get("data") or {}
        batch = d.get("positions") or []
        if total is None:
            total = d.get("count") or 0
        positions.extend(batch)
        start += PAGE
        if not batch or start >= total:
            break
        time.sleep(1.0)  # Eightfold rate-limits aggressive clients (HTTP 429)

    if location:
        # Eightfold's location search is distance-based and can return
        # nearby-country roles; keep only positions actually in the country.
        loc_l = location.lower()
        positions = [p for p in positions
                     if any(loc_l in (l or "").lower() for l in (p.get("locations") or []))
                     or (loc_l == "india" and any(
                         str(sl).strip().upper() == "IN" or str(sl).strip().upper().endswith(", IN")
                         or "india" in str(sl).lower()
                         for sl in (p.get("standardizedLocations") or [])))]

    jobs, details, seen = [], 0, set()
    for p in positions:
        pid = p.get("id")
        if pid in seen:
            continue
        seen.add(pid)
        title = p.get("name") or NOT_SPECIFIED
        url = f"https://{host}{p.get('positionUrl') or f'/careers/job/{pid}'}"
        locs = p.get("locations") or []
        description, employment = "", NOT_SPECIFIED
        if details < detail_cap and _is_cse_title(title):
            try:
                det = (request_json(f"{base}/position_details", tag=tag, max_retries=2,
                                    params={"position_id": pid, "domain": domain, "hl": "en"}) or {}).get("data") or {}
                description = det.get("jobDescription") or ""
                employment = (det.get("efcustomTextEmploymentType") or [NOT_SPECIFIED])[0]
                url = det.get("publicUrl") or url
                details += 1
                time.sleep(1.0)
            except RuntimeError as e:
                print(f"[{tag}] detail failed for {pid}: {e}")
        jobs.append(Job(
            company=company_display_name,
            job_title=title,
            job_id=str(p.get("displayJobId") or p.get("atsJobId") or pid),
            job_url=url, apply_url=url,
            location_raw="; ".join(locs) if locs else NOT_SPECIFIED,
            work_mode=(p.get("workLocationOption") or NOT_SPECIFIED).title(),
            employment_type=employment,
            technology_domain=p.get("department") or NOT_SPECIFIED,
            date_posted=_ts_to_date(p.get("postedTs")),
            job_description=description,
            source_website=host,
            source_type="eightfold_api",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ).to_dict())
    print(f"[{tag}] {company_display_name}: {len(jobs)} jobs fetched ({location}, {details} with description)")
    return jobs


def selftest():
    assert _ts_to_date(1791521307) == "2026-10-09"
    assert _ts_to_date(None) is None
    print("adapter_eightfold self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        print(len(fetch_eightfold_jobs(sys.argv[1], sys.argv[2])))
