"""
Fetch candidate career-site JSON endpoints found by probe_career_sites.py
with plain `requests` (no browser) and save the response shape plus the
first items, so adapters can be written against real field names.
Output: endpoint_dump.json
"""

import json
import re
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}

ORACLE_Q = ("onlyData=true&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber={site},"
            "facetsList=LOCATIONS,limit=5,location=India,sortBy=POSTING_DATES_DESC")

CALLS = [
    ("infosys", "GET", "https://intapgateway.infosysapps.com/careersci/search/intapjbsrch/getCareerSearchJobs?sourceId=1,21&searchText=ALL", None),
    ("oracle-facet-oracle", "GET", "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=locationsFacet&finder=findReqs;siteNumber=CX_45001,facetsList=LOCATIONS,limit=1", None),
    ("oracle-facet-dell", "GET", "https://enterpriseplatform.dell.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=locationsFacet&finder=findReqs;siteNumber=CX_1001,facetsList=LOCATIONS,limit=1", None),
    ("eightfold-microsoft", "GET", "https://apply.careers.microsoft.com/api/pcsx/search?domain=microsoft.com&query=&location=India&start=0", None),
    ("eightfold-microsoft-detail", "GET", "DETAIL_MS", None),
    ("eightfold-qualcomm", "GET", "https://careers.qualcomm.com/api/pcsx/search?domain=qualcomm.com&query=&location=India&start=0", None),
    ("eightfold-ericsson", "GET", "https://jobs.ericsson.com/api/pcsx/search?domain=ericsson.com&query=&location=India&start=0", None),
    ("eightfold-infineon", "GET", "https://jobs.infineon.com/api/pcsx/search?domain=infineon.com&query=&location=India&start=0", None),
    ("oracle-oracle", "GET", "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?" + ORACLE_Q.format(site="CX_45001"), None),
    ("oracle-dell", "GET", "https://enterpriseplatform.dell.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?" + ORACLE_Q.format(site="CX_1001"), None),
    ("oracle-nokia", "GET", "https://fa-evmr-saasfaprod1.fa.ocs.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?" + ORACLE_Q.format(site="CX_1"), None),
    ("oracle-ti", "GET", "https://edbz.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?" + ORACLE_Q.format(site="CX"), None),
    ("oracle-kpmg", "GET", "https://ejgk.fa.em2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?" + ORACLE_Q.format(site="CX_3"), None),
    ("oracle-kpmg-3001", "GET", "https://ejgk.fa.em2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?" + ORACLE_Q.format(site="CX_3001"), None),
    ("oracle-detail-ti", "GET", "DETAIL_ORACLE", None),
    ("jibe-amd", "GET", "https://careers.amd.com/api/jobs?location=India&page=1&sortBy=relevance&descending=false&internal=false", None),
    ("jibe-github", "GET", "https://www.github.careers/api/jobs?page=1&sortBy=relevance&descending=false&internal=false", None),
    ("ibm", "POST", "https://www-api.ibm.com/search/api/v2", {
        "appId": "careers", "scopes": ["careers2"], "query": {"bool": {"must": []}},
        "post_filter": {"term": {"field_keyword_05": "India"}}, "size": 3, "from": 0,
        "sort": [{"_score": "desc"}, {"pageviews": "desc"}], "lang": "zz", "localeSelector": {},
        "sm": {"query": "", "lang": "zz"},
        "_source": ["_id", "title", "url", "description", "language", "entitled", "field_keyword_17",
                    "field_keyword_08", "field_keyword_18", "field_keyword_19", "field_keyword_05"]}),
    ("atlassian", "GET", "https://www.atlassian.com/endpoint/careers/listings", None),
    ("phonepe", "GET", "https://www.phonepe.com/apollo/job-postings/latest.json", None),
    ("phonepe-sr", "GET", "https://api.smartrecruiters.com/v1/companies/PHONEPELIMITED/postings?limit=2", None),
    ("sharechat", "GET", "https://sharechat.com/api/careersList?limit=100", None),
    ("urbancompany", "POST", "https://www.urbanclap.com/api/v2/platform-gateway/getAllJobs", {}),
    ("capgemini", "GET", "https://cg-jobstream-api.azurewebsites.net/api/job-search?page=1&size=3&country_code=in-en", None),
    ("postman-json", "GET", "https://www.postman.com/_mk-www-next/api-cache/careers-jobs.json", None),
    ("lever-dreamsports", "GET", "https://api.lever.co/v0/postings/dreamsports?mode=json", None),
    ("nttdata-phenom", "POST", "https://careers.nttdata.com/widgets", {
        "lang": "en_global", "deviceType": "desktop", "country": "global", "pageName": "search-results",
        "ddoKey": "refineSearch", "sortBy": "", "subsearch": "", "from": 0, "jobs": True, "counts": True,
        "all_fields": ["category", "country", "state", "city", "type"], "size": 3, "clearAll": False,
        "jdsource": "facets", "isSliderEnable": False, "pageId": "page20", "siteType": "external",
        "keywords": "", "global": True, "selected_fields": {"country": ["India"]}, "locationData": {}}),
    ("workday-walmart", "POST", "https://walmart.wd5.myworkdayjobs.com/wday/cxs/walmart/WalmartExternal/jobs",
     {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}),
    ("workday-visa", "POST", "https://visa.wd5.myworkdayjobs.com/wday/cxs/visa/Visa/jobs",
     {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}),
    ("darwinbox-delhivery", "GET", "https://delhivery.darwinbox.in/ms/candidateapi/job?page=1&limit=5", None),
]

SF_SITES = {"wipro": "https://careers.wipro.com/search/?q=&locationsearch=India",
            "hcltech": "https://careers.hcltech.com/search/?q=&locationsearch=India",
            "ey": "https://careers.ey.com/ey/search/?q=&locationsearch=India"}


def shape(obj, depth=0):
    if depth > 5:
        return "..."
    if isinstance(obj, dict):
        return {k: shape(v, depth + 1) for k, v in list(obj.items())[:80]}
    if isinstance(obj, list):
        india = [shape(x, depth + 1) for x in obj if "india" in json.dumps(x).lower()][:5]
        return [f"list[{len(obj)}]", shape(obj[0], depth + 1) if obj else None, {"india_items": india}]
    if isinstance(obj, str):
        return obj[:160]
    return obj


def main():
    out = {}
    s = requests.Session()
    s.headers.update(UA)
    ms_first = ora_first = None
    for name, method, url, body in CALLS:
        if url == "DETAIL_MS":
            if not ms_first:
                continue
            url = f"https://apply.careers.microsoft.com/api/pcsx/position_details?position_id={ms_first}&domain=microsoft.com&hl=en"
        if url == "DETAIL_ORACLE":
            if not ora_first:
                continue
            url = ("https://edbz.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
                   f"?expand=all&onlyData=true&finder=ById;Id=%22{ora_first}%22,siteNumber=CX")
        try:
            r = s.request(method, url, json=body, timeout=30)
            entry = {"status": r.status_code, "ctype": r.headers.get("content-type"), "bytes": len(r.content)}
            try:
                data = r.json()
                entry["shape"] = shape(data)
                if name == "eightfold-microsoft":
                    pos = (data.get("data") or {}).get("positions") or []
                    ms_first = pos[0]["id"] if pos else None
                if name == "oracle-ti":
                    items = data.get("items") or []
                    rl = items[0].get("requisitionList") if items else []
                    ora_first = rl[0]["Id"] if rl else None
            except Exception:
                entry["text"] = r.text[:600]
        except Exception as e:
            entry = {"error": str(e)[:300]}
        out[name] = entry
        print(name, entry.get("status"), entry.get("bytes"), entry.get("error", ""), flush=True)

    for name, url in SF_SITES.items():
        try:
            ss = requests.Session()
            ss.headers.update(UA)
            page = ss.get(url, timeout=30)
            html = page.text
            m = re.search(r"""(?:CSRFToken|csrfToken|_csrf)["']?\s*[:=]\s*["']([\w-]{20,})""", html)
            entry = {"page_status": page.status_code, "csrf_found": bool(m),
                     "csrf_context": [html[max(0, i.start() - 80): i.start() + 80]
                                      for i in re.finditer(r"(?i)csrf", html)][:4]}
            if m:
                host = url.split("/")[2]
                r = ss.post(f"https://{host}/services/recruiting/v1/jobs",
                            json={"locale": "en_US", "pageNumber": 0, "sortBy": "", "keywords": "",
                                  "location": "India", "facetFilters": {}, "brand": "", "skills": [],
                                  "categoryId": 0, "alertId": "", "rcmCandidateId": ""},
                            headers={"x-csrf-token": m.group(1), "Content-Type": "application/json",
                                     "Referer": url}, timeout=30)
                entry["api_status"] = r.status_code
                try:
                    entry["shape"] = shape(r.json())
                except Exception:
                    entry["text"] = r.text[:600]
            # classic CSB HTML result rows
            entry["classic_rows"] = len(re.findall(r'class="jobTitle-link', html))
            entry["classic_sample"] = re.findall(r'<a[^>]+class="jobTitle-link[^"]*"[^>]*>[^<]+</a>', html)[:2]
        except Exception as e:
            entry = {"error": str(e)[:300]}
        out["sf-" + name] = entry
        print("sf-" + name, entry.get("page_status"), entry.get("api_status"), flush=True)

    with open("endpoint_dump.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
