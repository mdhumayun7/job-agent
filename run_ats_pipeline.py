"""
Runs the ATS-based company pipeline (Greenhouse/Lever/SmartRecruiters)
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "config"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "scrapers" / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "xlsx"))

COMPANIES_PATH = Path(__file__).resolve().parent / "config" / "companies.json"

ADAPTER_MAP = {}  # populated lazily below so this file can be unit-tested without network


def _load_adapters():
    from adapter_greenhouse import fetch_greenhouse_jobs
    from adapter_lever import fetch_lever_jobs
    from adapter_smartrecruiters import fetch_smartrecruiters_jobs
    from adapter_makemytrip import fetch_makemytrip_jobs
    ADAPTER_MAP["greenhouse"] = fetch_greenhouse_jobs
    ADAPTER_MAP["lever"] = fetch_lever_jobs
    ADAPTER_MAP["smartrecruiters"] = fetch_smartrecruiters_jobs
    # makemytrip_custom takes no slug -- wrap it to match the (slug, name) signature
    ADAPTER_MAP["makemytrip_custom"] = lambda slug, name: fetch_makemytrip_jobs(name)


def load_enabled_companies(companies_path=COMPANIES_PATH, company_filter=None, limit=None):
    """Pure logic, no network -- testable on its own."""
    companies = json.loads(Path(companies_path).read_text(encoding="utf-8"))
    enabled = [
        c for c in companies
        if c.get("enabled") and c.get("platform") in ("greenhouse", "lever", "smartrecruiters", "makemytrip_custom")
    ]
    if company_filter:
        enabled = [c for c in enabled if c["company"].lower() == company_filter.lower()]
    if limit:
        enabled = enabled[:limit]
    return enabled


def run(companies_path=COMPANIES_PATH, company_filter=None, limit=None):
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
    for entry in targets:
        platform = entry["platform"]
        slug = entry.get("verified_slug", entry["company"].lower())
        fetch_fn = ADAPTER_MAP.get(platform)
        if not fetch_fn:
            failures.append((entry["company"], f"no adapter for platform '{platform}'"))
            continue
        try:
            jobs = fetch_fn(slug, entry["company"])
            enriched = [enrich_job(j) for j in jobs]
            all_jobs.extend(enriched)
            fetched_companies.add(entry["company"].strip().lower())
        except Exception as e:
            failures.append((entry["company"], str(e)))
            print(f"[ats-pipeline] {entry['company']} FAILED: {e} -- continuing with other companies "
                  f"(its previously-seen jobs will NOT be marked closed this run)")

    print(f"\n[ats-pipeline] Companies attempted: {len(targets)} | Succeeded: {len(targets) - len(failures)} | Failed: {len(failures)}")
    for company, reason in failures:
        print(f"  FAILED: {company} -- {reason}")

    if not all_jobs:
        print("[ats-pipeline] No jobs collected from any company -- not writing an empty xlsx.")
        return {"total": 0, "failures": failures}

    from history import apply_history, save_history
    all_jobs, updated_history = apply_history(all_jobs, fetched_companies=fetched_companies)
    save_history(updated_history)
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
    args = parser.parse_args()
    run(company_filter=args.company, limit=args.limit)
