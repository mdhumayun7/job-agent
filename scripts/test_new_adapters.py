"""
Run adapters live against a list of (company, platform, slug) candidates and
record counts plus sample jobs -- evidence for enabling companies.
Output: probe_results.json (pushed to the probe-results branch by probe.yml).
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import run_ats_pipeline as rp  # noqa: E402

CANDIDATES = [
    ("Microsoft", "eightfold", "apply.careers.microsoft.com|microsoft.com"),
    ("Qualcomm", "eightfold", "careers.qualcomm.com|qualcomm.com"),
    ("Ericsson", "eightfold", "jobs.ericsson.com|ericsson.com"),
    ("Infineon Technologies", "eightfold", "jobs.infineon.com|infineon.com"),
    ("Oracle", "oracle_hcm", "eeho.fa.us2.oraclecloud.com|CX_45001"),
    ("Dell Technologies", "oracle_hcm", "enterpriseplatform.dell.com|CX_1001"),
    ("Nokia", "oracle_hcm", "fa-evmr-saasfaprod1.fa.ocs.oraclecloud.com|CX_1"),
    ("Texas Instruments", "oracle_hcm", "edbz.fa.us2.oraclecloud.com|CX"),
    ("KPMG", "oracle_hcm", "ejgk.fa.em2.oraclecloud.com|CX_3"),
    ("KPMG", "oracle_hcm", "ejgk.fa.em2.oraclecloud.com|CX_3001"),
    ("AMD", "jibe", "careers.amd.com|India"),
    ("GitHub", "jibe", "www.github.careers"),
    ("Wipro", "successfactors", "careers.wipro.com|/search/|India"),
    ("HCLTech", "successfactors", "careers.hcltech.com|/search/|"),
    ("EY", "successfactors", "careers.ey.com|/ey/search/|India"),
    ("NTT DATA", "phenom", "careers.nttdata.com|en_global|global|/global/en/job/"),
    ("Delhivery", "darwinbox", "delhivery"),
    ("IBM", "custom_api", "ibm"),
    ("Atlassian", "custom_api", "atlassian"),
    ("Capgemini", "custom_api", "capgemini"),
    ("ShareChat", "custom_api", "sharechat"),
    ("Urban Company", "custom_api", "urbancompany"),
    ("PhonePe", "smartrecruiters", "PHONEPELIMITED"),
    ("Visa", "workday", "visa.wd5.myworkdayjobs.com/visa/Visa"),
    ("Postman", "workday", "postman.wd108.myworkdayjobs.com/postman/careers"),
    ("Genpact", "workday", "genpact.wd108.myworkdayjobs.com/genpact/External_Careers"),
    ("BrowserStack", "workday", "browserstack.wd3.myworkdayjobs.com/browserstack/External"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    rp._load_adapters()
    out = []
    for company, platform, slug in CANDIDATES:
        if only and company not in only:
            continue
        t0 = time.time()
        rec = {"company": company, "platform": platform, "slug": slug}
        try:
            jobs = rp.ADAPTER_MAP[platform](slug, company)
            rec["count"] = len(jobs)
            rec["with_description"] = sum(1 for j in jobs if j.get("job_description"))
            rec["unique_ids"] = len({j.get("job_id") for j in jobs})
            rec["samples"] = [{k: (str(j.get(k))[:160]) for k in
                               ("job_title", "job_id", "location_raw", "job_url", "date_posted",
                                "employment_type", "technology_domain")} for j in jobs[:3]]
            described = [j for j in jobs if j.get("job_description")]
            rec["desc_sample"] = [(j.get("job_title"), (j.get("job_description") or "")[:300]) for j in described[:2]]
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"[:500]
            rec["trace"] = traceback.format_exc()[-1200:]
        rec["seconds"] = round(time.time() - t0, 1)
        print(f"{company:24} {platform:15} count={rec.get('count')} err={rec.get('error', '')[:120]}", flush=True)
        out.append(rec)
    Path("probe_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
