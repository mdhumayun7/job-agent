"""
Workday career-site adapter (generic, works for any company whose careers
page lives on <tenant>.wdN.myworkdayjobs.com).

Workday career sites are rendered from a public, unauthenticated JSON API
that the page itself calls:

  list:   POST https://{host}/wday/cxs/{tenant}/{site}/jobs
          body {"appliedFacets": {...}, "limit": 20, "offset": N, "searchText": ""}
  detail: GET  https://{host}/wday/cxs/{tenant}/{site}{externalPath}

The company is identified by a single string stored as `verified_slug` in
config/companies.json:  "{host}/{tenant}/{site}"
e.g. "nvidia.wd5.myworkdayjobs.com/nvidia/NVIDIAExternalCareerSite"

Large companies have thousands of postings worldwide, so by default this
adapter applies Workday's own "India" location facet when the site exposes
one (the platform is for students in India). If no India facet exists, it
falls back to the unfiltered list, capped at MAX_JOBS.

Full descriptions need one extra request per job, so they are only fetched
for CSE-relevant titles (up to DETAIL_CAP per company). Every other field
comes straight from the list response -- nothing is guessed.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from job_schema import Job, NOT_SPECIFIED  # noqa: E402
from _http import request_json  # noqa: E402

PAGE_SIZE = 20          # Workday rejects larger page sizes
MAX_JOBS = 400          # hard cap per company per run
DETAIL_CAP = 60         # max per-job detail requests per company per run
POLITE_DELAY = 0.3


def parse_slug(slug: str):
    parts = slug.strip("/").split("/")
    if len(parts) != 3:
        raise ValueError(f"workday slug must be 'host/tenant/site', got '{slug}'")
    return parts[0], parts[1], parts[2]


INDIA_MARKERS = ("india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "mumbai",
                 "gurgaon", "gurugram", "noida", "new delhi", "kolkata", "ahmedabad", "kochi",
                 "trivandrum", "thiruvananthapuram", "coimbatore", "mysore", "mysuru", "jaipur",
                 "chandigarh", "vadodara", "nagpur", "indore", "bhubaneswar", "mohali")


def _find_india_facet(facets):
    """Walk Workday's (sometimes nested) facet tree and return
    (facetParameter, [ids]) selecting India-located jobs.

    1. Prefer a country-level value whose descriptor is exactly 'India'.
    2. Otherwise many tenants only expose city-level values such as
       'Bangalore, India' or 'Hyderabad' -- select every location value that
       names India or a major Indian city, under the location facet with the
       most matches.
    Returns None if the site exposes no India location at all."""
    exact, partial = [], {}

    def walk(items, parent_param=None):
        for item in items or []:
            param = item.get("facetParameter") or parent_param
            values = item.get("values")
            if values:
                walk(values, param)
            desc = (item.get("descriptor") or "").strip().lower()
            if not desc or not item.get("id") or not param:
                continue
            if desc == "india":
                exact.append((param, item["id"]))
            elif "location" in param.lower() and any(m in desc for m in INDIA_MARKERS):
                partial.setdefault(param, []).append(item["id"])

    walk(facets)
    if exact:
        exact.sort(key=lambda c: 0 if "country" in c[0].lower() else 1)
        return exact[0][0], [exact[0][1]]
    if partial:
        param = max(partial, key=lambda k: len(partial[k]))
        return param, partial[param]
    return None


def _posted_on_to_iso(text):
    """Workday gives relative strings like 'Posted Today', 'Posted Yesterday',
    'Posted 3 Days Ago', 'Posted 30+ Days Ago'. Convert only the exact ones."""
    if not text:
        return None
    t = text.lower()
    now = datetime.now(timezone.utc)
    if "today" in t:
        return now.date().isoformat()
    if "yesterday" in t:
        return (now - timedelta(days=1)).date().isoformat()
    if "+" in t:
        return None  # "30+ days ago" -- exact date unknown, don't invent one
    digits = "".join(ch for ch in t if ch.isdigit())
    if digits and "day" in t:
        return (now - timedelta(days=int(digits))).date().isoformat()
    return None


def _is_cse_title(title):
    try:
        from parsers import detect_cse_relevance
        relevant, _ = detect_cse_relevance(title, "")
        return bool(relevant)
    except Exception:
        return False


def fetch_workday_jobs(slug: str, company_display_name: str, india_only: bool = True,
                       max_jobs: int = MAX_JOBS, detail_cap: int = DETAIL_CAP) -> list:
    host, tenant, site = parse_slug(slug)
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    list_url = f"{base}/jobs"
    tag = f"workday:{tenant}"

    first = request_json(list_url, method="POST", tag=tag,
                         json_body={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": 0, "searchText": ""})
    if first is None:
        print(f"[{tag}] career site not found (404): {slug}")
        return []

    applied = {}
    if india_only:
        facet = _find_india_facet(first.get("facets"))
        if facet:
            applied = {facet[0]: facet[1]}
            print(f"[{tag}] using India location facet ({facet[0]}, {len(facet[1])} value(s))")
        else:
            print(f"[{tag}] no India facet on this site -- fetching unfiltered (capped at {max_jobs})")

    postings = []
    total = None
    offset = 0
    while offset < max_jobs:
        if offset == 0 and not applied:
            page = first
        else:
            page = request_json(list_url, method="POST", tag=tag,
                                json_body={"appliedFacets": applied, "limit": PAGE_SIZE,
                                           "offset": offset, "searchText": ""})
            if page is None:
                break
        if total is None:
            total = page.get("total") or 0  # Workday only fills `total` on the first page
        batch = page.get("jobPostings") or []
        postings.extend(batch)
        offset += PAGE_SIZE
        if not batch or offset >= (total or 0):
            break
        time.sleep(POLITE_DELAY)

    jobs = []
    details_done = 0
    seen = set()
    for raw in postings:
        path = raw.get("externalPath")
        if not path or path in seen:
            continue
        seen.add(path)
        title = raw.get("title") or NOT_SPECIFIED
        req_id = (raw.get("bulletFields") or [None])[0]

        description = ""
        employment_type = NOT_SPECIFIED
        date_posted = _posted_on_to_iso(raw.get("postedOn"))
        location = raw.get("locationsText") or NOT_SPECIFIED
        public_url = f"https://{host}/{site}{path}"

        if details_done < detail_cap and _is_cse_title(title):
            try:
                detail = request_json(f"{base}{path}", tag=tag, max_retries=2) or {}
                info = detail.get("jobPostingInfo") or {}
                description = info.get("jobDescription") or ""
                employment_type = info.get("timeType") or NOT_SPECIFIED
                date_posted = info.get("startDate") or date_posted
                location = info.get("location") or location
                req_id = info.get("jobReqId") or req_id
                public_url = info.get("externalUrl") or public_url
                details_done += 1
                time.sleep(POLITE_DELAY)
            except RuntimeError as e:
                print(f"[{tag}] detail fetch failed for {path}: {e} -- keeping list fields only")

        job = Job(
            company=company_display_name,
            job_title=title,
            job_id=req_id or path,
            requisition_id=req_id,
            job_url=public_url,
            apply_url=public_url,
            location_raw=location,
            employment_type=employment_type,
            date_posted=date_posted,
            job_description=description,
            source_website=f"{host}/{site}",
            source_type="workday_api",
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )
        jobs.append(job.to_dict())

    scope = "India" if applied else "all locations"
    print(f"[{tag}] {company_display_name}: {len(jobs)} jobs fetched ({scope}, "
          f"{details_done} with full description)")
    return jobs


def selftest():
    facets = [
        {"facetParameter": "locationMainGroup", "values": [
            {"facetParameter": "locationCountry", "values": [
                {"descriptor": "United States of America", "id": "us1", "count": 900},
                {"descriptor": "India", "id": "in1", "count": 120},
            ]},
        ]},
        {"facetParameter": "jobFamilyGroup", "values": [{"descriptor": "Engineering", "id": "e1"}]},
    ]
    assert _find_india_facet(facets) == ("locationCountry", ["in1"]), _find_india_facet(facets)
    assert _find_india_facet([]) is None
    city_facets = [{"facetParameter": "locations", "values": [
        {"descriptor": "Bangalore, India", "id": "b1"}, {"descriptor": "San Jose, US", "id": "s1"},
        {"descriptor": "Hyderabad", "id": "h1"}]}]
    assert _find_india_facet(city_facets) == ("locations", ["b1", "h1"]), _find_india_facet(city_facets)
    assert _find_india_facet([{"facetParameter": "locations", "values": [
        {"descriptor": "Tokyo", "id": "t1"}]}]) is None
    assert parse_slug("nvidia.wd5.myworkdayjobs.com/nvidia/NVIDIAExternalCareerSite") == (
        "nvidia.wd5.myworkdayjobs.com", "nvidia", "NVIDIAExternalCareerSite")
    assert _posted_on_to_iso("Posted 30+ Days Ago") is None
    assert _posted_on_to_iso("Posted Today") == datetime.now(timezone.utc).date().isoformat()
    assert _posted_on_to_iso("Posted 3 Days Ago") is not None
    try:
        parse_slug("bad-slug")
        raise AssertionError("bad slug should raise")
    except ValueError:
        pass
    print("adapter_workday self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        s = sys.argv[1] if len(sys.argv) > 1 else "nvidia.wd5.myworkdayjobs.com/nvidia/NVIDIAExternalCareerSite"
        n = sys.argv[2] if len(sys.argv) > 2 else "NVIDIA"
        res = fetch_workday_jobs(s, n)
        print(f"Fetched {len(res)} jobs for {n}")
        if res:
            print(res[0]["job_title"], "-", res[0]["location_raw"])
