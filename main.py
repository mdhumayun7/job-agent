import argparse
import sys
from pathlib import Path
from datetime import datetime

from utils.helpers import log, save_results
from config import OUTPUT_FILE, EXCEL_FILE


def safe_console_text(value):
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _get_scraper(name):
    if name == "naukri":
        from scrapers.naukri_scraper import scrape_naukri
        return scrape_naukri
    if name == "linkedin":
        from scrapers.linkedin_scraper import scrape_linkedin
        return scrape_linkedin
    if name == "indeed":
        from scrapers.indeed_scraper import scrape_indeed
        return scrape_indeed
    if name == "angellist":
        from scrapers.angellist_scraper import scrape_angellist
        return scrape_angellist
    if name == "govt":
        from scrapers.govt_scraper import scrape_govt_sites
        return scrape_govt_sites
    return None


def run_scraper(name, retries=1):
    scraper = _get_scraper(name)
    if scraper is None:
        log.warning(f"Unknown scraper: {name}")
        return []

    for attempt in range(1, retries + 1):
        try:
            return scraper()
        except Exception as e:
            log.error(f"[{name}] Scraper failed on attempt {attempt}/{retries}: {e}")
            if attempt == retries:
                return []
            log.info(f"[{name}] Retrying scraper...")


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
        title = safe_console_text(j.get("title", ""))
        company = safe_console_text(j.get("company", ""))
        print(f"    {i}. [{j.get('match_score',0):>3}/100] {title} @ {company}")

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
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="Number of retry attempts for each scraper",
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
        results = run_scraper(site, retries=max(1, args.retries))
        all_jobs.extend(results)
        log.info(f"{site}: {len(results)} jobs")

    if not all_jobs:
        log.error("Koi jobs nahi mili.")
        sys.exit(1)

    final_jobs = save_results(all_jobs)
    print_summary(final_jobs, top_n=max(1, args.top))


if __name__ == "__main__":
    main()
