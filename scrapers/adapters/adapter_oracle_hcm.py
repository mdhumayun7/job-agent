"""
Oracle Recruiting Cloud (Oracle HCM "Candidate Experience") adapter.
Used by Oracle, Dell, Nokia, Texas Instruments, KPMG India, ...

The candidate-experience pages are rendered from Oracle's public REST API:
  list:   GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions
              ?onlyData=true&expand=requisitionList.secondaryLocations
              &finder=findReqs;siteNumber={site},limit=25,offset=N,location=India,sortBy=POSTING_DATES_DESC
  detail: GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails
              ?expand=all&onlyData=true&finder=ById;Id="{id}",siteNumber={site}

verified_slug format: "{host}|{siteNumber}"  e.g. "edbz.fa.us2.oraclecloud.com|CX"
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

PAGE = 100
MAX_SCAN = 4000
MAX_JOBS = 400
DETAIL_CAP = 40
HEADERS = {"Content-Type": "application/vnd.oracle.adf.resourceitem+json;charset=utf-8"}


def fetch_oracle_hcm_jobs(slug: str, company_display_name: str, location: str = "India",
                          max_jobs: int = MAX_JOBS, detail_cap: int = DETAIL_CAP) -> list:
    host, site = slug.split("|")
    tag = f"oracle:{site}@{host.split('.')[0]}"
    api = f"https://{host}/hcmRestApi/resources/latest"
    # Oracle's free-text "location=India" search only matches postings whose
    # location is literally the country on some sites (Oracle: 13 of hundreds).
    # So scan the whole site, newest first, and keep postings whose primary or
    # secondary location is in the country. Sites are a few thousand postings
    # at most, i.e. a few dozen requests.
    def in_country(r):
        if not location:
            return True
        code = (r.get("PrimaryLocationCountry") or "").upper()
        if location.lower() == "india" and code == "IN":
            return True
        locs = [r.get("PrimaryLocation") or ""] + [str((x or {}).get("Name") or "")
                                                   for x in (r.get("secondaryLocations") or [])]
        return any(location.lower() in l.lower() for l in locs)

    reqs, offset, total = [], 0, None
    while offset < MAX_SCAN and len(reqs) < max_jobs:
        finder = f"findReqs;siteNumber={site},limit={PAGE},offset={offset},sortBy=POSTING_DATES_DESC"
        url = (f"{api}/recruitingCEJobRequisitions?onlyData=true"
               f"&expand=requisitionList.secondaryLocations&finder={finder}")
        data = request_json(url, tag=tag, extra_headers=HEADERS)
        if data is None:
            print(f"[{tag}] site not found (404)")
            return []
        items = data.get("items") or []
        if not items:
            break
        head = items[0]
        if total is None:
            total = head.get("TotalJobsCount") or 0
        batch = head.get("requisitionList") or []
        reqs.extend(r for r in batch if in_country(r))
        offset += len(batch)
        if not batch or offset >= total:
            break
        time.sleep(0.3)
    reqs = reqs[:max_jobs]

    jobs, details, seen = [], 0, set()
    for r in reqs:
        rid = str(r.get("Id"))
        if rid in seen:
            continue
        seen.add(rid)
        title = r.get("Title") or NOT_SPECIFIED
        desc = r.get("ShortDescriptionStr") or ""
        if details < detail_cap and _is_cse_title(title):
            try:
                det = request_json(
                    f"{api}/recruitingCEJobRequisitionDetails?expand=all&onlyData=true"
                    f"&finder=ById;Id=%22{rid}%22,siteNumber={site}",
                    tag=tag, max_retries=2, extra_headers=HEADERS) or {}
                d = (det.get("items") or [{}])[0]
                desc = "\n\n".join(x for x in (d.get("ExternalDescriptionStr"),
                                               d.get("ExternalQualificationsStr"),
                                               d.get("ExternalResponsibilitiesStr")) if x) or desc
                details += 1
                time.sleep(0.3)
            except RuntimeError as e:
                print(f"[{tag}] detail failed for {rid}: {e}")
        locs = [r.get("PrimaryLocation")] + [s.get("Name") for s in (r.get("secondaryLocations") or [])
                                             if isinstance(s, dict)]
        url = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{rid}"
        jobs.append(Job(
            company=company_display_name,
            job_title=title,
            job_id=rid,
            job_url=url, apply_url=url,
            location_raw="; ".join(l for l in locs if l) or NOT_SPECIFIED,
            work_mode=r.get("WorkplaceType") or NOT_SPECIFIED,
            employment_type=r.get("JobSchedule") or r.get("WorkerType") or NOT_SPECIFIED,
            technology_domain=r.get("JobFamily") or r.get("JobFunction") or NOT_SPECIFIED,
            date_posted=r.get("PostedDate"),
            application_deadline=r.get("PostingEndDate"),
            job_description=desc,
            source_website=f"{host}/{site}",
            source_type="oracle_hcm_api",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        ).to_dict())
    print(f"[{tag}] {company_display_name}: {len(jobs)} jobs fetched ({location}, scanned {offset} of {total}, "
          f"{details} with full description)")
    return jobs


if __name__ == "__main__":
    print(len(fetch_oracle_hcm_jobs(sys.argv[1], sys.argv[2])))
