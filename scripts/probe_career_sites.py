"""
Automated "DevTools > Network" capture for companies that have no known
public ATS API.

Runs in GitHub Actions (real internet). For each target it opens the
company's job-search page in headless Chromium, records every JSON
XHR/fetch response the page makes (URL, method, POST body, size, and the
shape of the biggest list inside it), and every link/iframe pointing at a
known ATS. Output: probe_results.json. Nothing is enabled from this --
it is only evidence for writing adapters.

Usage: python scripts/probe_career_sites.py [--only "TCS,Infosys"]
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

TARGETS = {
    "TCS": ["https://ibegin.tcs.com/iBegin/jobs/search"],
    "Infosys": ["https://career.infosys.com/joblist"],
    "Wipro": ["https://careers.wipro.com/search/?q=&locationsearch=India"],
    "HCLTech": ["https://careers.hcltech.com/", "https://www.hcltech.com/careers/careers-in-india"],
    "Cognizant": ["https://careers.cognizant.com/global-en/jobs/?location=India"],
    "Deloitte": ["https://jobsindia.deloitte.com/search/?q=", "https://apply.deloitte.com/careers/SearchJobs"],
    "Capgemini": ["https://www.capgemini.com/in-en/careers/join-capgemini/job-search/"],
    "CGI": ["https://cgi.njoyn.com/corp/xweb/xweb.asp?NTKN=c&clid=21001&page=joblisting"],
    "Tech Mahindra": ["https://careers.techmahindra.com/"],
    "LTIMindtree": ["https://www.ltimindtree.com/careers/"],
    "Mphasis": ["https://careers.mphasis.com/home/jobs.html"],
    "Persistent Systems": ["https://www.persistent.com/careers/"],
    "Hexaware": ["https://jobs.hexaware.com/"],
    "Coforge": ["https://www.coforge.com/careers"],
    "NTT DATA": ["https://www.nttdata.com/global/en/careers"],
    "Genpact": ["https://www.genpact.com/careers"],
    "EY": ["https://careers.ey.com/ey/search/?q=&locationsearch=India"],
    "KPMG": ["https://kpmg.com/in/en/careers.html"],
    "Microsoft": ["https://jobs.careers.microsoft.com/global/en/search?lc=India", "https://apply.careers.microsoft.com/careers?location=India"],
    "Google": ["https://www.google.com/about/careers/applications/jobs/results/?location=India"],
    "Apple": ["https://jobs.apple.com/en-in/search?location=india-INDC"],
    "Meta": ["https://www.metacareers.com/jobs?offices[0]=Bangalore%2C%20India"],
    "IBM": ["https://www.ibm.com/careers/search?field_keyword_05[0]=India"],
    "AMD": ["https://careers.amd.com/careers-home/jobs?location=India"],
    "Qualcomm": ["https://careers.qualcomm.com/careers?location=India"],
    "Oracle": ["https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?location=India"],
    "SAP": ["https://jobs.sap.com/search/?q=&locationsearch=India"],
    "Dell Technologies": ["https://jobs.dell.com/en/location/india-jobs/375/1269750/2"],
    "Lenovo": ["https://jobs.lenovo.com/en_US/careers"],
    "Siemens": ["https://jobs.siemens.com/careers?location=India"],
    "Ericsson": ["https://jobs.ericsson.com/careers?location=India"],
    "Nokia": ["https://jobs.nokia.com/"],
    "Visa": ["https://corporate.visa.com/en/jobs/?cities=Bengaluru"],
    "Uber": ["https://www.uber.com/us/en/careers/list/?location=IND-Karnataka-Bangalore"],
    "GitHub": ["https://www.github.careers/careers-home/jobs"],
    "Atlassian": ["https://www.atlassian.com/company/careers/all-jobs"],
    "Flipkart": ["https://www.flipkartcareers.com/#!/joblist"],
    "Walmart Global Tech": ["https://walmart.wd5.myworkdayjobs.com/WalmartExternal", "https://careers.walmart.com/results?q=&page=1"],
    "PhonePe": ["https://www.phonepe.com/careers/job-openings/"],
    "Swiggy": ["https://careers.swiggy.com/#/careers"],
    "Zomato": ["https://www.zomato.com/careers"],
    "Zepto": ["https://www.zeptonow.com/careers"],
    "Myntra": ["https://careers.myntra.com/job-listing/"],
    "Nykaa": ["https://www.nykaa.com/careers"],
    "Dream11": ["https://www.dreamsports.group/careers/"],
    "Ola": ["https://www.olacabs.com/careers"],
    "Ola Electric": ["https://www.olaelectric.com/careers"],
    "Delhivery": ["https://www.delhivery.com/careers"],
    "Udaan": ["https://udaan.com/careers"],
    "ShareChat": ["https://sharechat.com/careers"],
    "Practo": ["https://www.practo.com/company/careers"],
    "BYJU'S": ["https://byjus.com/careers/"],
    "Physics Wallah": ["https://www.pw.live/careers"],
    "CoinDCX": ["https://careers.coindcx.com/"],
    "Policybazaar": ["https://www.pbfintech.in/careers/"],
    "Urban Company": ["https://careers.urbancompany.com/"],
    "OYO": ["https://www.oyorooms.com/careers/"],
    "Zerodha": ["https://zerodha.com/careers/"],
    "Zoho": ["https://careers.zohocorp.com/jobs/Careers"],
    "Postman": ["https://www.postman.com/company/careers/open-positions/"],
    "BrowserStack": ["https://www.browserstack.com/careers"],
    "Chargebee": ["https://www.chargebee.com/careers/"],
    "Juspay": ["https://juspay.io/careers"],
    "MediaTek": ["https://careers.mediatek.com/eREC/JobSearch"],
    "Texas Instruments": ["https://careers.ti.com/en/sites/CX/jobs?location=India"],
    "Arm": ["https://careers.arm.com/search-jobs/India"],
    "STMicroelectronics": ["https://www.st.com/content/st_com/en/about/careers/job-search.html"],
    "Infineon Technologies": ["https://jobs.infineon.com/careers?location=India"],
    "Synopsys": ["https://careers.synopsys.com/search-jobs/India"],
    "Lam Research": ["https://careers.lamresearch.com/search-jobs"],
    "ASML": ["https://www.asml.com/en/careers/find-your-job?job_country=India"],
    "BMC Software": ["https://jobs.bmc.com/"],
}

ATS_PATTERNS = [
    r"[\w-]+\.wd\d+\.myworkdayjobs\.com/[\w-]+(?:/[\w-]+)?",
    r"boards(?:-api)?\.greenhouse\.io/[\w-]+", r"job-boards\.greenhouse\.io/[\w-]+",
    r"jobs\.lever\.co/[\w-]+", r"jobs\.smartrecruiters\.com/[\w-]+",
    r"jobs\.ashbyhq\.com/[\w-]+", r"apply\.workable\.com/[\w-]+",
    r"[\w-]+\.darwinbox\.in", r"[\w-]+\.keka\.com", r"[\w-]+\.freshteam\.com",
    r"[\w-]+\.zohorecruit\.\w+", r"[\w.-]+\.oraclecloud\.com/hcmUI/CandidateExperience[^\"' ]*",
    r"[\w.-]+\.taleo\.net[^\"' ]*", r"[\w.-]+\.icims\.com", r"[\w.-]+\.eightfold\.ai",
    r"[\w.-]+\.successfactors\.\w+[^\"' ]*", r"[\w.-]+\.jobvite\.com/[\w-]+",
    r"[\w.-]+\.recruitee\.com", r"[\w.-]+\.teamtailor\.com", r"[\w.-]+\.bamboohr\.com",
    r"cdn\.phenompeople\.com[^\"' ]*", r"phApp\.refNum\s*=\s*['\"]?\w+",
    r'"refNum"\s*:\s*"\w+"',
]

SKIP_URL = re.compile(r"(google-analytics|googletagmanager|doubleclick|facebook|hotjar|clarity\.ms|"
                      r"segment|newrelic|onetrust|cookielaw|optimizely|adobedtm|demdex|linkedin\.com/px|"
                      r"sentry|datadoghq|fullstory|bing\.com|twitter|yandex)", re.I)


def biggest_list(obj, path="$", depth=0):
    """Return (length, path, keys_of_first_item) of the largest list of dicts."""
    best = (0, None, None)
    if depth > 6:
        return best
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict):
            best = (len(obj), path, sorted(obj[0].keys())[:40])
        for i, v in enumerate(obj[:3]):
            cand = biggest_list(v, f"{path}[{i}]", depth + 1)
            if cand[0] > best[0]:
                best = cand
    elif isinstance(obj, dict):
        for k, v in obj.items():
            cand = biggest_list(v, f"{path}.{k}", depth + 1)
            if cand[0] > best[0]:
                best = cand
    return best


def probe(page, company, url):
    captured = []

    def on_response(resp):
        try:
            req = resp.request
            if req.resource_type not in ("xhr", "fetch") or SKIP_URL.search(resp.url):
                return
            ctype = (resp.headers.get("content-type") or "").lower()
            if "json" not in ctype:
                return
            body = resp.text()
            data = json.loads(body)
            n, path, keys = biggest_list(data)
            captured.append({
                "url": resp.url[:600], "method": req.method, "status": resp.status,
                "post_data": (req.post_data or "")[:1500], "bytes": len(body),
                "list_len": n, "list_path": path, "item_keys": keys,
                "req_headers": {k: v for k, v in req.headers.items()
                                if k.lower() in ("content-type", "x-csrf-token", "x-apple-csrf-token",
                                                 "authorization", "x-requested-with", "referer", "origin")},
            })
        except Exception:
            pass

    page.on("response", on_response)
    result = {"company": company, "url": url}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        for _ in range(3):
            page.mouse.wheel(0, 4000)
            time.sleep(1.5)
        html = page.content()
        result["final_url"] = page.url
        result["title"] = page.title()[:200]
        frames = [f.url for f in page.frames if f.url and f.url != "about:blank"]
        hits = set()
        for pat in ATS_PATTERNS:
            for m in re.findall(pat, html + " " + " ".join(frames)):
                hits.add(m[:200])
        result["ats_hits"] = sorted(hits)[:40]
        result["frames"] = frames[:10]
        result["html_bytes"] = len(html)
    except Exception as e:
        result["error"] = str(e)[:300]
    page.remove_listener("response", on_response)
    captured.sort(key=lambda c: -c["list_len"])
    result["json_calls"] = captured[:15]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--out", default="probe_results.json")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",")} if args.only else None

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/128.0 Safari/537.36",
            locale="en-IN", viewport={"width": 1366, "height": 900})
        for company, urls in TARGETS.items():
            if only and company not in only:
                continue
            for url in urls:
                page = ctx.new_page()
                r = probe(page, company, url)
                page.close()
                best = r["json_calls"][0]["list_len"] if r.get("json_calls") else 0
                print(f"{company:24} json_calls={len(r.get('json_calls', []))} biggest_list={best} "
                      f"ats={len(r.get('ats_hits', []))} {r.get('error', '')}", flush=True)
                results.append(r)
        browser.close()
    Path(args.out).write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    sys.exit(main())
