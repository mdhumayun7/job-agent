import json, re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from config import ENRICHED_OUTPUT_FILE, JOBS_FILE

def load_jobs():
    src = Path(ENRICHED_OUTPUT_FILE) if Path(ENRICHED_OUTPUT_FILE).exists() else Path(JOBS_FILE)
    with open(src, "r", encoding="utf-8") as f:
        return json.load(f)

def save_jobs(jobs):
    with open(ENRICHED_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(jobs)} jobs")

# ── 1. Job Expiry Detection ───────────────────────────────────────────────────
def remove_expired(jobs, days=7):
    cutoff = datetime.now() - timedelta(days=days)
    fresh = []
    expired = 0
    for job in jobs:
        posted = job.get("posted_date", "")
        if not posted:
            fresh.append(job)
            continue
        try:
            # Handle "X days ago" format
            if "day" in str(posted).lower():
                num = int(re.search(r"\d+", str(posted)).group())
                if num <= days:
                    fresh.append(job)
                else:
                    expired += 1
            elif "hour" in str(posted).lower() or "minute" in str(posted).lower():
                fresh.append(job)
            elif len(str(posted)) >= 10:
                post_date = datetime.fromisoformat(str(posted)[:10])
                if post_date >= cutoff:
                    fresh.append(job)
                else:
                    expired += 1
            else:
                fresh.append(job)
        except:
            fresh.append(job)
    print(f"  Expiry Filter: {len(jobs)} → {len(fresh)} jobs ({expired} expired removed)")
    return fresh

# ── 2. Duplicate Company Filter ───────────────────────────────────────────────
def filter_duplicate_companies(jobs, max_per_company=2):
    company_count = defaultdict(int)
    filtered = []
    for job in sorted(jobs, key=lambda j: j.get("ai_match_score", j.get("match_score",0)), reverse=True):
        company = job.get("company","").strip().lower()
        if not company:
            filtered.append(job)
            continue
        if company_count[company] < max_per_company:
            filtered.append(job)
            company_count[company] += 1
    print(f"  Company Dedup: {len(jobs)} → {len(filtered)} jobs (max {max_per_company} per company)")
    return filtered

# ── 3. Salary Parser ──────────────────────────────────────────────────────────
def parse_salary(salary_str):
    if not salary_str: return None, None
    s = str(salary_str).lower().replace(",","")
    nums = re.findall(r"\d+\.?\d*", s)
    if not nums: return None, None
    nums = [float(n) for n in nums]
    # Convert monthly to annual
    if "month" in s or "/month" in s or "per month" in s:
        nums = [n * 12 / 100000 for n in nums]  # to LPA
    # Already in LPA/lakhs
    elif "lpa" in s or "lakh" in s or "lac" in s:
        pass  # already LPA
    # In thousands
    elif max(nums) < 100:
        pass  # assume LPA
    else:
        nums = [n / 100000 for n in nums]  # convert to LPA
    lo = min(nums) if nums else None
    hi = max(nums) if nums else None
    return lo, hi

def enrich_salary(jobs):
    for job in jobs:
        lo, hi = parse_salary(job.get("salary",""))
        job["salary_min_lpa"] = round(lo, 1) if lo else None
        job["salary_max_lpa"] = round(hi, 1) if hi else None
        job["salary_known"] = lo is not None
    known = sum(1 for j in jobs if j.get("salary_known"))
    print(f"  Salary Parsed: {known}/{len(jobs)} jobs have salary data")
    return jobs

# ── 4. Company Blacklist ──────────────────────────────────────────────────────
BLACKLIST_FILE = "data/blacklist.json"

def load_blacklist():
    p = Path(BLACKLIST_FILE)
    if not p.exists(): return []
    with open(p) as f: return json.load(f)

def save_blacklist(companies):
    Path(BLACKLIST_FILE).parent.mkdir(exist_ok=True)
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(companies, f, indent=2)

def apply_blacklist(jobs):
    blacklist = [c.lower() for c in load_blacklist()]
    if not blacklist: return jobs
    filtered = [j for j in jobs if j.get("company","").lower() not in blacklist]
    print(f"  Blacklist: {len(jobs)} → {len(filtered)} jobs ({len(jobs)-len(filtered)} removed)")
    return filtered

def add_to_blacklist(company):
    bl = load_blacklist()
    if company.lower() not in [c.lower() for c in bl]:
        bl.append(company)
        save_blacklist(bl)
        print(f"  Added '{company}' to blacklist")

# ── Main ──────────────────────────────────────────────────────────────────────
def run_filters(jobs=None, expiry_days=7, max_per_company=2):
    if jobs is None:
        jobs = load_jobs()
    print(f"\n{'='*50}")
    print(f"  Smart Filters | {len(jobs)} jobs")
    print(f"{'='*50}")
    jobs = apply_blacklist(jobs)
    jobs = remove_expired(jobs, days=expiry_days)
    jobs = enrich_salary(jobs)
    jobs = filter_duplicate_companies(jobs, max_per_company=max_per_company)
    jobs = sorted(jobs, key=lambda j: j.get("ai_match_score",j.get("match_score",0)), reverse=True)
    save_jobs(jobs)
    print(f"\n  Final: {len(jobs)} jobs after all filters")
    return jobs

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--max-per-company", type=int, default=2)
    parser.add_argument("--blacklist", type=str, help="Add company to blacklist")
    args = parser.parse_args()
    if args.blacklist:
        add_to_blacklist(args.blacklist)
    run_filters(expiry_days=args.days, max_per_company=args.max_per_company)
