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

PAGE = 25
MAX_JOBS = 400
DETAIL_CAP = 40
HEADERS = {"Content-Type": "application/vnd.oracle.adf.resourceitem+json;charset=utf-8"}


def fetch_oracle_hcm_jobs(slug: str, company_display_name: str, location: str = "India",
                          max_jobs: int = MAX_JOBS, detail_cap: int = DETAIL_CAP) -> list:
    host, site = slug.split("|")
    tag = f"oracle:{site}@{host.split('.')[0]}"
    api = f"https://{host}/hcmRestApi/resources/latest"
    # Prefer the site's own country facet (exact), fall back to the free-text
    # location search, which on some sites only matches a literal "India".
    loc_filter = f"location={location}"
    facet_url = (f"{api}/recruitingCEJobRequisitions?onlyData=true&expand=locationsFacet"
                 f"&finder=findReqs;siteNumber={site},facetsList=LOCATIONS,limit=1")
    try:
        fdata = request_json(facet_url, tag=tag, extra_headers=HEADERS) or {}
        facets = ((fdata.get("items") or [{}])[0].get("locationsFacet")) or []
        match = [f for f in facets if (f.get("Name") or "").strip().lower() == location.lower()]
        if match:
            loc_filter = f"selectedLocationsFacet={match[0]['Id']}"
            print(f"[{tag}] using location facet {location} ({match[0].get('TotalCount')} jobs)")
    except RuntimeError as e:
        print(f"[{tag}] facet lookup failed ({e}); using text location search")

    reqs, offset, total = [], 0, None
    while offset < max_jobs:
        finder = (f"findReqs;siteNumber={site},limit={PAGE},offset={offset},"
                  f"{loc_filter},sortBy=POSTING_DATES_DESC")
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
        reqs.extend(batch)
        offset += PAGE
        if not batch or offset >= total:
            break
        time.sleep(0.3)

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
    print(f"[{tag}] {company_display_name}: {len(jobs)} jobs fetched ({location}, total={total}, "
          f"{details} with full description)")
    return jobs


if __name__ == "__main__":
    print(len(fetch_oracle_hcm_jobs(sys.argv[1], sys.argv[2])))
