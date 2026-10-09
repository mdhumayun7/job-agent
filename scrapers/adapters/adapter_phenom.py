"""
Phenom People career-site adapter (NTT DATA, ...).

Phenom sites load search results from their own widgets endpoint:
  POST https://{host}/widgets   {"ddoKey": "refineSearch", "from": N, "size": 50, ...}

verified_slug format: "{host}|{lang}|{site_country}|{job_url_prefix}"
  e.g. "careers.nttdata.com|en_global|global|/global/en/job/"
Scoped to country India via the site's own country facet.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED  # noqa: E402
from _http import request_json  # noqa: E402

PAGE = 50
MAX_JOBS = 500


def fetch_phenom_jobs(slug: str, company_display_name: str, country_filter: str = "India") -> list:
    host, lang, site_country, job_prefix = slug.split("|")
    tag = f"phenom:{host}"
    jobs, offset, total = [], 0, None
    while offset < MAX_JOBS:
        body = {"lang": lang, "deviceType": "desktop", "country": site_country, "pageName": "search-results",
                "ddoKey": "refineSearch", "sortBy": "Most recent", "subsearch": "", "from": offset,
                "jobs": True, "counts": True, "all_fields": ["category", "country", "state", "city", "type"],
                "size": PAGE, "clearAll": False, "jdsource": "facets", "isSliderEnable": False,
                "pageId": "page20", "siteType": "external", "keywords": "", "global": True,
                "selected_fields": {"country": [country_filter]} if country_filter else {}, "locationData": {}}
        data = request_json(f"https://{host}/widgets", method="POST", json_body=body, tag=tag)
        if data is None:
            print(f"[{tag}] widgets endpoint not found (404)")
            return []
        rs = data.get("refineSearch") or {}
        if total is None:
            total = rs.get("totalHits") or 0
        batch = (rs.get("data") or {}).get("jobs") or []
        for j in batch:
            jid = j.get("jobId") or j.get("reqId") or j.get("jobSeqNo")
            url = j.get("applyUrl") if not jid else f"https://{host}{job_prefix}{jid}"
            loc = j.get("location") or ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
            jobs.append(Job(
                company=company_display_name,
                job_title=j.get("title") or NOT_SPECIFIED,
                job_id=str(jid) if jid else None,
                job_url=url or "", apply_url=j.get("applyUrl") or url or "",
                location_raw=loc or NOT_SPECIFIED,
                city=j.get("city"), state_region=j.get("state"), country=j.get("country"),
                employment_type=j.get("type") or NOT_SPECIFIED,
                technology_domain=j.get("category") or NOT_SPECIFIED,
                date_posted=(j.get("postedDate") or j.get("dateCreated") or "")[:10] or None,
                job_description=j.get("descriptionTeaser") or "",
                experience_raw=j.get("experienceLevel") or NOT_SPECIFIED,
                source_website=host, source_type="phenom_api",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ).to_dict())
        offset += PAGE
        if not batch or offset >= total:
            break
        time.sleep(0.3)
    print(f"[{tag}] {company_display_name}: {len(jobs)} jobs fetched ({country_filter}, total={total})")
    return jobs


if __name__ == "__main__":
    print(len(fetch_phenom_jobs(sys.argv[1], sys.argv[2])))
