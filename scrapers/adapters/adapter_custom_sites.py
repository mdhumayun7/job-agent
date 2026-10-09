"""
Company-specific career-site adapters. Each function reads the public JSON
endpoint that the company's own careers page calls (found with
scripts/probe_career_sites.py). Field names are company-specific.

Registered in CUSTOM_FETCHERS; companies.json uses
  "platform": "custom_api", "verified_slug": "<key>"
"""

import re
import sys
import time
import html as htmlmod
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED  # noqa: E402
from _http import request_json  # noqa: E402


def _now():
    return datetime.now(timezone.utc).isoformat()


def _epoch_date(v):
    try:
        n = float(v)
        if n > 1e11:  # milliseconds
            n /= 1000
        return datetime.fromtimestamp(int(n), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return str(v)[:10] if v else None


def _text(v):
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", v or "")).strip()


# ---------------------------------------------------------------- IBM
def fetch_ibm(name="IBM", max_jobs=1500):
    """IBM careers search (Elasticsearch-backed), scoped to India."""
    jobs, offset, total = [], 0, None
    while offset < max_jobs:
        body = {"appId": "careers", "scopes": ["careers2"], "query": {"bool": {"must": []}},
                "post_filter": {"term": {"field_keyword_05": "India"}}, "size": 100, "from": offset,
                "sort": [{"_score": "desc"}, {"pageviews": "desc"}], "lang": "zz", "localeSelector": {},
                "sm": {"query": "", "lang": "zz"},
                "_source": ["_id", "title", "url", "description", "field_keyword_17", "field_keyword_08",
                            "field_keyword_18", "field_keyword_19", "field_keyword_05", "dcdate"]}
        data = request_json("https://www-api.ibm.com/search/api/v2", method="POST", json_body=body, tag="ibm")
        if data is None:
            raise RuntimeError("IBM search API returned 404")
        hits = data.get("hits") or {}
        if total is None:
            total = (hits.get("total") or {}).get("value") or 0
        batch = hits.get("hits") or []
        for h in batch:
            s = h.get("_source") or {}
            url = s.get("url") or ""
            jid = re.search(r"(\d{4,})", url)
            loc = ", ".join(x for x in (s.get("field_keyword_19"), s.get("field_keyword_05")) if x)
            jobs.append(Job(
                company=name, job_title=s.get("title") or NOT_SPECIFIED,
                job_id=jid.group(1) if jid else h.get("_id"),
                job_url=url, apply_url=url, location_raw=loc or "India",
                technology_domain=s.get("field_keyword_08") or NOT_SPECIFIED,
                experience_raw=s.get("field_keyword_18") or NOT_SPECIFIED,
                employment_type=s.get("field_keyword_17") or NOT_SPECIFIED,
                date_posted=(s.get("dcdate") or "")[:10] or None,
                job_description=s.get("description") or "",
                source_website="ibm.com/careers", source_type="ibm_search_api", scraped_at=_now(),
            ).to_dict())
        offset += 100
        if not batch or offset >= total:
            break
        time.sleep(0.3)
    print(f"[ibm] {name}: {len(jobs)} jobs fetched (India, total={total})")
    return jobs


# ---------------------------------------------------------------- Atlassian
def fetch_atlassian(name="Atlassian"):
    data = request_json("https://www.atlassian.com/endpoint/careers/listings", tag="atlassian")
    if data is None:
        raise RuntimeError("Atlassian listings endpoint returned 404")
    jobs = []
    for j in data:
        post = j.get("portalJobPost") or {}
        url = post.get("portalUrl") or j.get("applyUrl") or ""
        desc = "\n\n".join(x for x in (j.get("overview"), j.get("responsibilities"), j.get("qualifications")) if x)
        updated = post.get("updatedDate")
        try:
            updated = datetime.strptime(updated, "%Y-%m-%d %I:%M %p").date().isoformat()
        except (TypeError, ValueError):
            updated = None
        jobs.append(Job(
            company=name, job_title=j.get("title") or NOT_SPECIFIED, job_id=str(j.get("id")),
            job_url=url, apply_url=j.get("applyUrl") or url,
            location_raw="; ".join(j.get("locations") or []) or NOT_SPECIFIED,
            employment_type=j.get("type") or NOT_SPECIFIED,
            technology_domain=j.get("category") or NOT_SPECIFIED,
            last_updated=updated, job_description=desc,
            source_website="atlassian.com/company/careers", source_type="atlassian_api", scraped_at=_now(),
        ).to_dict())
    print(f"[atlassian] {name}: {len(jobs)} jobs fetched")
    return jobs


# ---------------------------------------------------------------- Capgemini
def fetch_capgemini(name="Capgemini", max_jobs=1000):
    jobs, page, total = [], 1, None
    while len(jobs) < max_jobs:
        data = request_json("https://cg-jobstream-api.azurewebsites.net/api/job-search", tag="capgemini",
                            params={"page": page, "size": 100, "country_code": "in-en"})
        if data is None:
            raise RuntimeError("Capgemini job-search API returned 404")
        if total is None:
            total = data.get("count") or data.get("total") or 0
        batch = data.get("data") or []
        for j in batch:
            url = j.get("apply_job_url") or ""
            jobs.append(Job(
                company=name, job_title=j.get("title") or NOT_SPECIFIED,
                job_id=j.get("ref") or j.get("id"),
                job_url=url, apply_url=url, location_raw=j.get("location") or NOT_SPECIFIED,
                country="India", employment_type=j.get("contract_type") or NOT_SPECIFIED,
                technology_domain=j.get("professional_communities") or NOT_SPECIFIED,
                experience_raw=j.get("experience_level") or NOT_SPECIFIED,
                last_updated=j.get("updated_at"), date_posted=(j.get("indexed_at") or "")[:10] or None,
                job_description=j.get("description_stripped") or _text(j.get("description")),
                source_website="capgemini.com/in-en/careers", source_type="capgemini_api", scraped_at=_now(),
            ).to_dict())
        page += 1
        if not batch or len(jobs) >= total:
            break
        time.sleep(0.3)
    print(f"[capgemini] {name}: {len(jobs)} jobs fetched (India, total={total})")
    return jobs


# ---------------------------------------------------------------- ShareChat
def fetch_sharechat(name="ShareChat"):
    data = request_json("https://sharechat.com/api/careersList", tag="sharechat", params={"limit": 100})
    if data is None:
        raise RuntimeError("ShareChat careersList returned 404")
    jobs = []
    for group in ((data.get("data") or {}).get("careersList") or []):
        for j in group.get("data") or []:
            rid = j.get("requisitionId") or j.get("id")
            title = j.get("requisitionTitle") or j.get("designation") or j.get("roleName") or NOT_SPECIFIED
            url = f"https://sharechat.com/careers/{rid}" if rid else "https://sharechat.com/careers"
            lo, hi = j.get("yrsOfExpMin"), j.get("yrsOfExpMax")
            jobs.append(Job(
                company=name, job_title=title, job_id=str(rid) if rid else None,
                job_url=url, apply_url=url,
                location_raw="; ".join(j.get("officeLocationNames") or []) or NOT_SPECIFIED,
                employment_type=j.get("employmentType") or NOT_SPECIFIED,
                technology_domain=group.get("title") or j.get("orgUnitName") or NOT_SPECIFIED,
                experience_raw=f"{lo}-{hi} years" if lo is not None and hi is not None else NOT_SPECIFIED,
                date_posted=_epoch_date(j.get("approvedDate") or j.get("createdDate")),
                job_description=j.get("jobDescription") or "",
                source_website="sharechat.com/careers", source_type="sharechat_api", scraped_at=_now(),
            ).to_dict())
    print(f"[sharechat] {name}: {len(jobs)} jobs fetched")
    return jobs


# ---------------------------------------------------------------- Urban Company
def fetch_urbancompany(name="Urban Company"):
    data = request_json("https://www.urbanclap.com/api/v2/platform-gateway/getAllJobs", method="POST",
                        json_body={}, tag="urbancompany")
    if data is None:
        raise RuntimeError("Urban Company getAllJobs returned 404")
    jobs = []
    for j in data.get("jobs") or []:
        url = j.get("apply_url") or ""
        loc = j.get("location_city") or j.get("location") or []
        jobs.append(Job(
            company=name, job_title=j.get("job_title") or NOT_SPECIFIED,
            job_id=j.get("job_code") or j.get("job_id"),
            job_url=url, apply_url=url,
            location_raw="; ".join(str(x) for x in loc) if isinstance(loc, list) else (loc or NOT_SPECIFIED),
            technology_domain=j.get("parent_department") or NOT_SPECIFIED,
            job_description=j.get("job_description") or "",
            source_website="careers.urbancompany.com", source_type="urbancompany_api", scraped_at=_now(),
        ).to_dict())
    print(f"[urbancompany] {name}: {len(jobs)} jobs fetched")
    return jobs


CUSTOM_FETCHERS = {
    "ibm": fetch_ibm,
    "atlassian": fetch_atlassian,
    "capgemini": fetch_capgemini,
    "sharechat": fetch_sharechat,
    "urbancompany": fetch_urbancompany,
}


def fetch_custom_api_jobs(key: str, company_display_name: str) -> list:
    if key not in CUSTOM_FETCHERS:
        raise RuntimeError(f"no custom fetcher registered for '{key}'")
    return CUSTOM_FETCHERS[key](company_display_name)


if __name__ == "__main__":
    print(len(fetch_custom_api_jobs(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])))
