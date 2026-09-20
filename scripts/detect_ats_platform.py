"""
Run this from a machine with real internet access (your laptop, or a
GitHub Actions job) -- NOT from a sandboxed dev environment.

It takes a list of candidate slugs per company and checks which, if any,
resolve on Greenhouse / Lever / SmartRecruiters public APIs. It writes
verified results back into companies.json. Nothing is marked "enabled"
until this script has actually confirmed it -- no platform is guessed.

Usage:
    python detect_ats_platform.py

Reads: config/companies.json (must have "candidate_slugs": [...] per company)
Writes: config/companies.json (fills in "platform" and "verified_slug")
"""

import json
import time
import requests
from pathlib import Path

CONFIG_PATH = Path("config/companies.json")
TIMEOUT = 10

CHECKS = {
    "greenhouse": lambda slug: f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": lambda slug: f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1",
    "smartrecruiters": lambda slug: f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
}


def check_slug(platform: str, slug: str) -> bool:
    url = CHECKS[platform](slug)
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return False
        data = resp.json()
        # A non-existent slug on all three of these APIs returns HTTP 200
        # with an EMPTY list -- not a 404. So we must check length, not
        # just "did we get valid JSON back".
        if isinstance(data, list):
            return len(data) > 0
        if isinstance(data, dict):
            jobs = data.get("jobs")
            content = data.get("content")
            if isinstance(jobs, list):
                return len(jobs) > 0
            if isinstance(content, list):
                return len(content) > 0
            return False
        return False
    except Exception:
        return False


def main():
    companies = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    changed = False

    for entry in companies:
        if entry.get("platform") not in (None, "unverified"):
            continue  # already checked previously

        found = None
        for slug in entry.get("candidate_slugs", []):
            for platform in ("greenhouse", "lever", "smartrecruiters"):
                if check_slug(platform, slug):
                    found = (platform, slug)
                    break
            if found:
                break
            time.sleep(0.5)  # be polite -- these are shared public APIs

        if found:
            entry["platform"], entry["verified_slug"] = found
            entry["enabled"] = True
            print(f"[FOUND] {entry['company']}: {found[0]} ({found[1]})")
        else:
            entry["platform"] = "custom"
            entry["enabled"] = False
            print(f"[NOT FOUND] {entry['company']}: no known ATS API matched -- "
                  f"needs a custom scraper or manual verification of career_url")
        changed = True

    if changed:
        CONFIG_PATH.write_text(json.dumps(companies, indent=2), encoding="utf-8")
        print(f"\nUpdated {CONFIG_PATH}")
    else:
        print("Nothing to verify -- all companies already checked.")


def selftest():
    """Sanity check: a garbage slug must return False on all platforms.
    Run this first to prove the false-positive bug is actually fixed."""
    garbage = "this-company-definitely-does-not-exist-xyz123"
    print("Running self-test with a slug that should NOT exist...")
    any_false_positive = False
    for platform in CHECKS:
        result = check_slug(platform, garbage)
        print(f"  {platform}: {'FALSE POSITIVE (bug still present!)' if result else 'correctly returned False'}")
        any_false_positive = any_false_positive or result
    if any_false_positive:
        print("\nSELF-TEST FAILED -- do not trust the results below.")
    else:
        print("\nSelf-test passed. Proceeding with real detection.\n")
    return not any_false_positive


if __name__ == "__main__":
    import sys
    if not selftest():
        sys.exit(1)
    main()
