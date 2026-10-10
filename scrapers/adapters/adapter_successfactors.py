"""
SAP SuccessFactors Career Site Builder adapter (Wipro, HCLTech, EY, ...).

Two generations of CSB sites exist:
  * new:     the search page sets an X-CSRF-Token and calls
             POST https://{host}/services/recruiting/v1/jobs  (JSON)
  * classic: the search page itself is server-rendered HTML:
             GET https://{host}/{path}/search/?q=&locationsearch=India&startrow=N
             with one <tr class="data-row"> per job.

verified_slug format: "{host}|{search_path}|{location}"
  e.g. "careers.wipro.com|/search/|India"  or  "careers.ey.com|/ey/search/|India"
The adapter tries the JSON API first and falls back to the HTML table.
"""

import html as htmlmod
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
from job_schema import Job, NOT_SPECIFIED  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
MAX_JOBS = 600
CSRF_RE = re.compile(r"""(?:CSRFToken|csrfToken|X-CSRF-Token)["']?\s*[:=]\s*["']([\w-]{20,})""")


def _request(session, method, url, **kw):
    last = None
    for attempt in range(3):
        try:
            return session.request(method, url, timeout=30, **kw)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"successfactors request failed: {url} -- {last}")


def _clean(text):
    return htmlmod.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _norm_date(v):
    if not v:
        return None
    v = str(v).strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(v[:10] if fmt == "%Y-%m-%d" else v, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _flat(v):
    if isinstance(v, list):
        v = "; ".join(_flat(x) for x in v if x)
    elif isinstance(v, dict):
        v = v.get("name") or v.get("label") or v.get("value") or ""
    return re.sub(r"\s+", " ", _clean(str(v or "")).replace("<br/>", " ")).strip(" ;")


def _job(company, title, jid, url, location, date, host):
    location = _flat(location) if location else None
    date = _norm_date(date) if date and not re.match(r"\d{4}-\d{2}-\d{2}$", str(date)) else date
    return Job(
        company=company, job_title=title or NOT_SPECIFIED, job_id=str(jid) if jid else None,
        job_url=url, apply_url=url, location_raw=location or NOT_SPECIFIED, date_posted=date,
        source_website=host, source_type="successfactors_csb",
        scraped_at=datetime.now(timezone.utc).isoformat(),
    ).to_dict()


def _fetch_new_api(s, host, search_url, token, location, company):
    jobs, page, total = [], 0, None
    while len(jobs) < MAX_JOBS:
        r = _request(s, "POST", f"https://{host}/services/recruiting/v1/jobs",
                     json={"locale": "en_US", "pageNumber": page, "sortBy": "", "keywords": "",
                           "location": location, "facetFilters": {}, "brand": "", "skills": [],
                           "categoryId": 0, "alertId": "", "rcmCandidateId": ""},
                     headers={"x-csrf-token": token, "Content-Type": "application/json",
                              "Referer": search_url})
        if r.status_code != 200:
            return None
        data = r.json()
        if total is None:
            total = data.get("totalJobs") or 0
        batch = [x.get("response") or {} for x in (data.get("jobSearchResult") or [])]
        for j in batch:
            jid = j.get("id")
            url_title = j.get("urlTitle") or j.get("unifiedUrlTitle") or "job"
            url = f"https://{host}/job/{url_title}/{jid}-en_US/" if jid else search_url
            loc = (j.get("jobLocationShort") or j.get("sfstd_jobLocation_obj")
                   or ", ".join(_flat(x) for x in (j.get("jobLocationState"), j.get("jobLocationCountry")) if x))
            date = j.get("unifiedStandardStart") or None
            jobs.append(_job(company, j.get("unifiedStandardTitle") or j.get("title"), jid, url,
                             loc, date, host))
        page += 1
        if not batch or len(jobs) >= total:
            break
        time.sleep(0.3)
    return jobs, total


def _fetch_classic(s, host, path, location, company):
    jobs, startrow, total = [], 0, None
    while len(jobs) < MAX_JOBS:
        url = f"https://{host}{path}?q=&locationsearch={location}&startrow={startrow}"
        r = _request(s, "GET", url)
        if r.status_code != 200:
            break
        page = r.text
        if total is None:
            m = re.search(r'paginationLabel[^>]*>[^<]*?of\s*<b>([\d,]+)</b>', page) or \
                re.search(r'of\s*<b>([\d,]+)</b>', page)
            total = int(m.group(1).replace(",", "")) if m else 0
        rows = page.split('class="data-row')[1:]
        added = 0
        seen = {j["job_id"] for j in jobs}
        for row in rows:
            m = re.search(r'<a[^>]+href="([^"]+)"[^>]*class="jobTitle-link[^"]*"[^>]*>([^<]+)</a>', row) or \
                re.search(r'<a[^>]+class="jobTitle-link[^"]*"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', row)
            if not m:
                continue
            href, title = m.group(1), _clean(m.group(2))
            idm = re.search(r"/(\d{6,})/?", href)
            jid = idm.group(1) if idm else href
            if jid in seen:
                continue
            seen.add(jid)
            loc = re.search(r'class="jobLocation"[^>]*>(.*?)</span>', row, re.S)
            date = re.search(r'class="jobDate"[^>]*>(.*?)</span>', row, re.S)
            parsed_date = None
            if date:
                for fmt in ("%b %d, %Y", "%d %b %Y", "%m/%d/%Y", "%d/%m/%Y"):
                    try:
                        parsed_date = datetime.strptime(_clean(date.group(1)), fmt).date().isoformat()
                        break
                    except ValueError:
                        pass
            jobs.append(_job(company, title, jid, f"https://{host}{href}",
                             _clean(loc.group(1)) if loc else None, parsed_date, host))
            added += 1
        if not added:
            break
        startrow += 25
        if total and startrow >= total:
            break
        time.sleep(0.3)
    return jobs, total


DETAIL_CAP = 60
LDJSON_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
DESC_PATTERNS = [
    re.compile(r'itemprop="description"[^>]*>(.*?)</(?:span|div)>\s*</(?:span|div)>', re.S | re.I),
    re.compile(r'class="jobdescription"[^>]*>(.*?)</span>\s*</', re.S | re.I),
    re.compile(r'itemprop="description"[^>]*>(.*?)</span>', re.S | re.I),
]


def extract_description(page_html: str) -> str:
    """Job description from a CSB job page: schema.org JobPosting JSON-LD
    first, then the microdata / classic description containers."""
    import json as _json
    for block in LDJSON_RE.findall(page_html):
        try:
            data = _json.loads(block.strip())
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting" and item.get("description"):
                return _clean(item["description"])
    for rx in DESC_PATTERNS:
        m = rx.search(page_html)
        if m and len(_clean(m.group(1))) > 80:
            return _clean(m.group(1))
    return ""


def _add_descriptions(s, jobs, cap=DETAIL_CAP):
    """Descriptions need one page fetch per job, so only CSE-relevant titles
    get one (the ones the matcher and fresher filter actually need)."""
    try:
        from parsers import detect_cse_relevance
    except ImportError:
        return 0
    done = 0
    for j in jobs:
        if done >= cap:
            break
        if not detect_cse_relevance(j.get("job_title") or "", "")[0] or not j.get("job_url", "").startswith("http"):
            continue
        try:
            r = _request(s, "GET", j["job_url"])
            if r.status_code == 200:
                j["job_description"] = extract_description(r.text)
                done += 1 if j["job_description"] else 0
        except RuntimeError:
            pass
        time.sleep(0.3)
    return done


def fetch_successfactors_jobs(slug: str, company_display_name: str) -> list:
    host, path, location = (slug.split("|") + ["", ""])[:3]
    path = path or "/search/"
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "text/html,application/json"})
    search_url = f"https://{host}{path}?q=&locationsearch={location}"
    page = _request(s, "GET", search_url)
    if page.status_code == 404:
        print(f"[successfactors] {host}{path} not found (404)")
        return []
    if page.status_code >= 400:
        raise RuntimeError(f"successfactors search page returned HTTP {page.status_code}")
    m = CSRF_RE.search(page.text)
    result = None
    if m and 'data-row' not in page.text:
        result = _fetch_new_api(s, host, search_url, m.group(1), location, company_display_name)
    mode = "api"
    if result is None:
        result = _fetch_classic(s, host, path, location, company_display_name)
        mode = "html"
    jobs, total = result
    with_desc = _add_descriptions(s, jobs)
    print(f"[successfactors] {company_display_name}: {len(jobs)} jobs fetched ({mode}, location={location or 'all'}, "
          f"total={total}, {with_desc} with description)")
    return jobs


def selftest():
    row = ('<tr class="data-row"><td><a href="/ey/job/Chennai-Senior-TN-600032/1434300833/" '
           'class="jobTitle-link">RC FS Senior</a><span class="jobLocation"> Chennai, TN, IN </span>'
           '<span class="jobDate">Oct 8, 2026</span></td></tr>')

    class FakeResp:
        status_code = 200
        text = '<span class="paginationLabel">Results 1 - 1 of <b>1</b></span>' + row

    class FakeSession:
        def request(self, *a, **k):
            return FakeResp()

    jobs, total = _fetch_classic(FakeSession(), "careers.ey.com", "/ey/search/", "India", "EY")
    assert total == 1 and len(jobs) == 1, (total, jobs)
    j = jobs[0]
    assert j["job_id"] == "1434300833" and j["location_raw"] == "Chennai, TN, IN"
    assert j["date_posted"] == "2026-10-08" and j["job_title"] == "RC FS Senior"
    ld = ('<script type="application/ld+json">{"@type":"JobPosting","title":"x",'
          '"description":"<p>Build services in Python. 0-2 years.</p>"}</script>')
    assert extract_description(ld) == "Build services in Python. 0-2 years.", extract_description(ld)
    micro = '<span itemprop="description"><span>' + "We need a backend engineer. " * 5 + '</span></span>'
    assert extract_description(micro).startswith("We need a backend engineer"), extract_description(micro)
    assert extract_description("<html>nothing</html>") == ""
    print("adapter_successfactors self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        print(len(fetch_successfactors_jobs(sys.argv[1], sys.argv[2])))
