import argparse
import sys
from pathlib import Path
from datetime import datetime

from utils.helpers import log, deduplicate, save_results
from config import OUTPUT_FILE, EXCEL_FILE


def run_scraper(name):
    try:
        if name == "naukri":
            from scrapers.naukri_scraper import scrape_naukri
            return scrape_naukri()
        elif name == "linkedin":
            from scrapers.linkedin_scraper import scrape_linkedin
            return scrape_linkedin()
        elif name == "indeed":
            from scrapers.indeed_scraper import scrape_indeed
            return scrape_indeed()
        elif name == "angellist":
            from scrapers.angellist_scraper import scrape_angellist
            return scrape_angellist()
        elif name == "govt":
            from scrapers.govt_scraper import scrape_govt_sites
            return scrape_govt_sites()
        else:
            log.warning(f"Unknown scraper: {name}")
            return []
    except Exception as e:
        log.error(f"[{name}] Scraper failed: {e}")
        return []


def print_summary(jobs, top_n=20):
    print("\n" + "="*55)
    print("  JOB SEARCH COMPLETE")
    print("="*55)
    print(f"  Total jobs found : {len(jobs)}")

    sources = {}
    for j in jobs:
        s = j.get("source", "Unknown")
        sources[s] = sources.get(s, 0) + 1

    print("\n  By source:")
    for s, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"    {s:<25} {count} jobs")

    print(f"\n  Top {top_n} matches:")
    top = sorted(jobs, key=lambda x: x.get("match_score", 0), reverse=True)[:top_n]
    for i, j in enumerate(top, 1):
        print(f"    {i}. [{j.get('match_score',0):>3}/100] {j['title']} @ {j['company']}")

    print(f"\n  Excel file : {EXCEL_FILE}")
    print(f"  JSON file  : {OUTPUT_FILE}")
    print("="*55 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Job Search Agent")
    parser.add_argument(
        "--sites", nargs="+",
        choices=["naukri", "linkedin", "indeed", "angellist", "govt", "all"],
        default=["all"],
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top jobs to show in the final summary",
    )
    args = parser.parse_args()

    all_sites = ["naukri", "linkedin", "indeed", "angellist", "govt"]
    sites_to_run = all_sites if "all" in args.sites else args.sites

    Path("logs").mkdir(exist_ok=True)
    Path("output").mkdir(exist_ok=True)

    log.info(f"Starting | Sites: {sites_to_run} | {datetime.now().strftime('%H:%M:%S')}")

    all_jobs = []
    for site in sites_to_run:
        log.info(f"Running: {site.upper()}")
        results = run_scraper(site)
        all_jobs.extend(results)
        log.info(f"{site}: {len(results)} jobs")

    if not all_jobs:
        log.error("Koi jobs nahi mili.")
        sys.exit(1)

    unique_jobs = deduplicate(all_jobs)
    save_results(unique_jobs)
    print_summary(unique_jobs, top_n=max(1, args.top))


if __name__ == "__main__":
    main()
