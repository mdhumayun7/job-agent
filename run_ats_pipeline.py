"""
Runs the ATS-based company pipeline (Greenhouse/Lever/SmartRecruiters/
Ashby/Workable/Workday plus company-specific APIs such as MakeMyTrip, Amazon)
independently of the existing portal scrapers in main.py. Separate
schema, separate output file -- does not touch save_results() or
excel_exporter.py, so nothing existing can break.

Usage:
    python run_ats_pipeline.py                 # all enabled companies
    python run_ats_pipeline.py --company Stripe # just one, for testing
    python run_ats_pipeline.py --limit 2        # only first N companies (dry-run-ish)
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scrapers" / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "xlsx"))

COMPANIES_PATH = Path(__file__).resolve().parent / "config" / "companies.json"

SUPPORTED_PLATFORMS = ("greenhouse", "lever", "smartrecruiters", "ashby", "workable",
                       "workday", "makemytrip_custom", "amazon_custom", "eightfold", "oracle_hcm",
                       "jibe", "successfactors", "phenom", "darwinbox", "custom_api", "govt_notices")

ADAPTER_MAP = {}  # populated lazily below so this file can be unit-tested without network


def _load_adapters():
    from adapter_greenhouse import fetch_greenhouse_jobs
    from adapter_lever import fetch_lever_jobs
    from adapter_smartrecruiters import fetch_smartrecruiters_jobs
    from adapter_makemytrip import fetch_makemytrip_jobs
    from adapter_workday import fetch_workday_jobs
    from adapter_ashby import fetch_ashby_jobs
    from adapter_workable import fetch_workable_jobs
    from adapter_amazon import fetch_amazon_jobs
    from adapter_eightfold import fetch_eightfold_jobs
    from adapter_oracle_hcm import fetch_oracle_hcm_jobs
    from adapter_jibe import fetch_jibe_jobs
    from adapter_successfactors import fetch_successfactors_jobs
    from adapter_phenom import fetch_phenom_jobs
    from adapter_darwinbox import fetch_darwinbox_jobs
    from adapter_custom_sites import fetch_custom_api_jobs
    from adapter_govt_notices import fetch_govt_notices
    ADAPTER_MAP["greenhouse"] = fetch_greenhouse_jobs
    ADAPTER_MAP["lever"] = fetch_lever_jobs
    ADAPTER_MAP["smartrecruiters"] = fetch_smartrecruiters_jobs
    # makemytrip_custom takes no slug -- wrap it to match the (slug, name) signature
    ADAPTER_MAP["makemytrip_custom"] = lambda slug, name: fetch_makemytrip_jobs(name)
    ADAPTER_MAP["workday"] = fetch_workday_jobs
    ADAPTER_MAP["ashby"] = fetch_ashby_jobs
    ADAPTER_MAP["workable"] = fetch_workable_jobs
    ADAPTER_MAP["amazon_custom"] = lambda slug, name: fetch_amazon_jobs(name)
    ADAPTER_MAP["eightfold"] = fetch_eightfold_jobs
    ADAPTER_MAP["oracle_hcm"] = fetch_oracle_hcm_jobs
    ADAPTER_MAP["jibe"] = fetch_jibe_jobs
    ADAPTER_MAP["successfactors"] = fetch_successfactors_jobs
    ADAPTER_MAP["phenom"] = fetch_phenom_jobs
    ADAPTER_MAP["darwinbox"] = fetch_darwinbox_jobs
    ADAPTER_MAP["custom_api"] = fetch_custom_api_jobs
    ADAPTER_MAP["govt_notices"] = fetch_govt_notices


def load_enabled_companies(companies_path=COMPANIES_PATH, company_filter=None, limit=None):
    """Pure logic, no network -- testable on its own."""
    companies = json.loads(Path(companies_path).read_text(encoding="utf-8"))
    enabled = [
        c for c in companies
        if c.get("enabled") and c.get("platform") in SUPPORTED_PLATFORMS
    ]
    if company_filter:
        enabled = [c for c in enabled if c["company"].lower() == company_filter.lower()]
    if limit:
        enabled = enabled[:limit]
    return enabled


def run(companies_path=COMPANIES_PATH, company_filter=None, limit=None, workers=8):
    _load_adapters()
    from parsers import enrich_job
    from xlsx_generator import generate_xlsx

    targets = load_enabled_companies(companies_path, company_filter, limit)
    if not targets:
        print("[ats-pipeline] No enabled Greenhouse/Lever companies matched. "
              "Run scripts/detect_ats_platform.py first, or check --company spelling.")
        return {"total": 0}

    all_jobs = []
    failures = []
    fetched_companies = set()
    run_stats = {}

    def fetch_one(entry):
        platform = entry["platform"]
        slug = entry.get("verified_slug", entry["company"].lower())
        fetch_fn = ADAPTER_MAP.get(platform)
        t0 = time.time()
        if not fetch_fn:
            return entry, None, f"no adapter for platform '{platform}'", 0.0
        try:
            return entry, fetch_fn(slug, entry["company"]), None, time.time() - t0
        except Exception as e:  # noqa: BLE001 -- one company must never stop the others
            return entry, None, str(e), time.time() - t0

    # Companies are fetched in parallel: each is a different host, so this
    # does not increase load on any single site, and it cuts the run time.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for entry, jobs, error, secs in pool.map(fetch_one, targets):
            name = entry["company"]
            if error is not None:
                failures.append((name, error))
                run_stats[name] = {"ok": False, "count": 0, "seconds": round(secs, 1), "error": error[:300],
                                   "platform": entry["platform"]}
                print(f"[ats-pipeline] {name} FAILED: {error} -- continuing with other companies "
                      f"(its previously-seen jobs will NOT be marked closed this run)")
                continue
            all_jobs.extend(enrich_job(j) for j in jobs)
            fetched_companies.add(name.strip().lower())
            run_stats[name] = {"ok": True, "count": len(jobs), "seconds": round(secs, 1),
                               "platform": entry["platform"]}

    Path("output").mkdir(exist_ok=True)
    Path("output/company_run_stats.json").write_text(json.dumps(run_stats, indent=2), encoding="utf-8")

    print(f"\n[ats-pipeline] Companies attempted: {len(targets)} | Succeeded: {len(targets) - len(failures)} | Failed: {len(failures)}")
    for company, reason in failures:
        print(f"  FAILED: {company} -- {reason}")

    if not all_jobs:
        print("[ats-pipeline] No jobs collected from any company -- not writing an empty xlsx.")
        return {"total": 0, "failures": failures}

    from history import apply_history, save_history
    all_jobs, updated_history = apply_history(all_jobs, fetched_companies=fetched_companies)
    save_history(updated_history)
    from matching import apply_matching, top_matches
    for j in all_jobs:
        apply_matching(j)
    best = top_matches(all_jobs)
    Path("output").mkdir(exist_ok=True)
    Path("output/top_matches.json").write_text(json.dumps(best, indent=2, default=str), encoding="utf-8")
    india = sum(1 for j in all_jobs if j.get("country_scope") in ("India", "Remote-India"))
    print(f"[ats-pipeline] India/Remote-India jobs: {india} | Top matches (score >= threshold): {len(best)}")
    for j in best[:10]:
        print(f"    {j['match_score']:3d}  {j['company']}: {j['job_title']} ({j.get('location_raw')})")

    status_counts = {}
    for j in all_jobs:
        status_counts[j["status"]] = status_counts.get(j["status"], 0) + 1
    print(f"[ats-pipeline] Status breakdown: {status_counts}")

    Path("output").mkdir(exist_ok=True)
    result = generate_xlsx(all_jobs, "output/ats_jobs.xlsx")
    Path("output/ats_jobs.json").write_text(json.dumps(all_jobs, indent=2, default=str), encoding="utf-8")

    print(f"\n[ats-pipeline] {result}")
    print("[ats-pipeline] Written: output/ats_jobs.xlsx, output/ats_jobs.json")
    return {**result, "failures": failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", default=None, help="Run only this one company (for testing)")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N enabled companies")
    parser.add_argument("--workers", type=int, default=8, help="Companies fetched in parallel")
    args = parser.parse_args()
    t0 = time.time()
    run(company_filter=args.company, limit=args.limit, workers=args.workers)
    print(f"[ats-pipeline] finished in {time.time() - t0:.0f}s")
