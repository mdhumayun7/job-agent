"""
Darwinbox careers adapter (Delhivery and many other Indian companies).

Darwinbox candidate portals are backed by a public JSON endpoint:
  GET https://{sub}.darwinbox.in/ms/candidateapi/job?page=N&limit=50

verified_slug: the Darwinbox subdomain, e.g. "delhivery"
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED  # noqa: E402
from _http import request_json  # noqa: E402

LIMIT = 50
MAX_PAGES = 20


def _join(v):
    if isinstance(v, list):
        return "; ".join(str(x) for x in v if x)
    return v or ""


def fetch_darwinbox_jobs(sub: str, company_display_name: str) -> list:
    host = f"{sub}.darwinbox.in"
    tag = f"darwinbox:{sub}"
    jobs, page, total = [], 1, None
    while page <= MAX_PAGES:
        data = request_json(f"https://{host}/ms/candidateapi/job", tag=tag, params={"page": page, "limit": LIMIT})
        if data is None:
            print(f"[{tag}] portal not found (404)")
            return []
        msg = data.get("message") or {}
        if not isinstance(msg, dict):
            break
        if total is None:
            total = int(msg.get("jobscount") or 0)
        batch = msg.get("jobs") or []
        for j in batch:
            jid = j.get("id")
            url = f"https://{host}/ms/candidate/careers/{jid}" if jid else f"https://{host}/ms/candidate/careers"
            exp_from, exp_to = j.get("experience_from_num"), j.get("experience_to_num")
            exp = f"{exp_from}-{exp_to} years" if exp_from not in (None, "") and exp_to not in (None, "") else NOT_SPECIFIED
            jobs.append(Job(
                company=company_display_name,
                job_title=j.get("title") or j.get("designation_display_name") or NOT_SPECIFIED,
                job_id=str(jid) if jid else None,
                job_url=url, apply_url=url,
                location_raw=_join(j.get("officelocation_show_arr") or j.get("officelocation_arr")) or NOT_SPECIFIED,
                employment_type=j.get("emp_type") or NOT_SPECIFIED,
                technology_domain=j.get("department") or j.get("functional_area") or NOT_SPECIFIED,
                date_posted=j.get("job_posting_on") or j.get("created_on"),
                experience_raw=exp,
                source_website=host, source_type="darwinbox_api",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ).to_dict())
        if not batch or len(jobs) >= total:
            break
        page += 1
        time.sleep(0.3)
    print(f"[{tag}] {company_display_name}: {len(jobs)} jobs fetched (total={total})")
    return jobs


if __name__ == "__main__":
    print(len(fetch_darwinbox_jobs(sys.argv[1], sys.argv[2])))
