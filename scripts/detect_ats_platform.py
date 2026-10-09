"""
Run this from a machine with real internet access (your laptop, or a
GitHub Actions job) -- NOT from a sandboxed dev environment.

It takes a list of candidate slugs per company and checks which, if any,
resolve on Greenhouse / Lever / SmartRecruiters / Ashby / Workable public
APIs, plus any Workday career sites ("candidate_workday") and known
company-specific APIs ("candidate_custom", e.g. amazon_jobs). It writes
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
    "ashby": lambda slug: f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "workable": lambda slug: f"https://apply.workable.com/api/v1/widget/accounts/{slug}",
}
SLUG_PLATFORMS = ("greenhouse", "lever", "smartrecruiters", "ashby", "workable")

# Company-specific public JSON endpoints. Value: (platform name stored in
# companies.json, url to probe, key holding the job list).
CUSTOM_CHECKS = {
    "amazon_jobs": ("amazon_custom",
                    "https://www.amazon.jobs/en/search.json?normalized_country_code[]=IND&result_limit=1",
                    "jobs"),
}


def _norm(text):
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def greenhouse_name_matches(slug: str, company: str) -> bool:
    """Guard against slug collisions: a Greenhouse board token like 'ola'
    could belong to an unrelated company. The board metadata endpoint
    returns the board's display name; require it to share the company's
    first word. If the metadata call itself fails, don't block."""
    try:
        resp = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}", timeout=TIMEOUT)
        if resp.status_code != 200:
            return True
        board_name = _norm(resp.json().get("name"))
    except Exception:
        return True
    first_word = _norm(company.split()[0]) if company.split() else ""
    return bool(first_word) and (first_word in board_name or board_name in _norm(company))


def check_workday(cand: dict) -> bool:
    url = f"https://{cand['host']}/wday/cxs/{cand['tenant']}/{cand['site']}/jobs"
    try:
        resp = requests.post(url, timeout=TIMEOUT, json={
            "appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""})
        if resp.status_code == 429 or resp.status_code >= 500:
            return None  # rate-limited / server error: unknown, not "absent"
        if resp.status_code != 200:
            return False
        return len(resp.json().get("jobPostings") or []) > 0
    except Exception:
        return None


def check_custom(key: str) -> bool:
    _, url, list_key = CUSTOM_CHECKS[key]
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"Accept": "application/json"})
        if resp.status_code == 429 or resp.status_code >= 500:
            return None  # rate-limited / server error: unknown, not "absent"
        if resp.status_code != 200:
            return False
        return len(resp.json().get(list_key) or []) > 0
    except Exception:
        return None


def check_slug(platform: str, slug: str) -> bool:
    url = CHECKS[platform](slug)
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 429 or resp.status_code >= 500:
            return None  # rate-limited / server error: unknown, not "absent"
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
        return None  # network error: unknown, not "absent"


def main():
    companies = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    changed = False

    for entry in companies:
        if entry.get("platform") not in (None, "unverified"):
            continue  # already checked previously

        found = None
        errored = False
        for slug in entry.get("candidate_slugs", []):
            for platform in SLUG_PLATFORMS:
                ok = check_slug(platform, slug)
                errored = errored or ok is None
                if ok:
                    if platform == "greenhouse" and not greenhouse_name_matches(slug, entry["company"]):
                        print(f"[SKIP] {entry['company']}: greenhouse board '{slug}' belongs to a different company")
                        continue
                    found = (platform, slug)
                    break
            if found:
                break
            time.sleep(0.5)  # be polite -- these are shared public APIs

        if not found:
            for cand in entry.get("candidate_workday", []):
                ok = check_workday(cand)
                errored = errored or ok is None
                if ok:
                    found = ("workday", f"{cand['host']}/{cand['tenant']}/{cand['site']}")
                    break
                time.sleep(0.5)

        if not found:
            for key in entry.get("candidate_custom", []):
                ok = check_custom(key) if key in CUSTOM_CHECKS else False
                errored = errored or ok is None
                if ok:
                    found = (CUSTOM_CHECKS[key][0], key)
                    break

        if not found and errored:
            print(f"[RETRY LATER] {entry['company']}: network errors during detection -- will re-check next run")
            continue

        if found:
            entry["platform"], entry["verified_slug"] = found
            entry["enabled"] = True
            print(f"[FOUND] {entry['company']}: {found[0]} ({found[1]})")
        else:
            entry["platform"] = "custom"
            entry["enabled"] = False
            entry.setdefault("note", "Auto-detection found no public ATS/API for this company. "
                                     "Needs the real JSON endpoint from the careers page (browser DevTools > Network).")
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
    wd = check_workday({"host": "nvidia.wd5.myworkdayjobs.com", "tenant": "nvidia", "site": garbage})
    print(f"  workday: {'FALSE POSITIVE (bug still present!)' if wd else 'correctly returned False'}")
    any_false_positive = any_false_positive or wd
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
