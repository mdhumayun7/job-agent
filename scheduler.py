import subprocess, sys, time
from datetime import datetime
from pathlib import Path

SITES = "naukri linkedin indeed internshala shine"

def run(cmd, label):
    print(f"\n▶ {label}...")
    start = time.time()
    result = subprocess.run(cmd, shell=True)
    duration = round(time.time()-start, 1)
    status = "✅" if result.returncode == 0 else "⚠️"
    print(f"  {status} {label} done in {duration}s")
    return result.returncode == 0

def pipeline():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*55}")
    print(f"  🚀 Job Agent Pipeline — {ts}")
    print(f"{'='*55}")
    Path("logs").mkdir(exist_ok=True)
    Path("output").mkdir(exist_ok=True)
    Path("data").mkdir(exist_ok=True)

    steps = [
        (f"python main.py --sites {SITES} --retries 1", "1. Scraping Jobs"),
        ("python phase2_enrichment.py",                 "2. AI Enrichment"),
        ("python smart_filters.py",                     "3. Smart Filters"),
        ("python resume_tailor.py",                     "4. Resume Tailoring"),
        ("python interview_prep.py",                    "5. Interview Prep"),
        ("python excel_exporter.py",                    "6. Excel Export"),
        ("python report_generator.py --top 20",         "7. Daily Report"),
        ("python analytics.py",                         "8. Analytics"),
    ]

    results = []
    for cmd, label in steps:
        ok = run(cmd, label)
        results.append((label, ok))

    print(f"\n{'='*55}")
    print("  ✅ Pipeline Summary")
    print(f"{'='*55}")
    for label, ok in results:
        print(f"  {'✅' if ok else '❌'}  {label}")
    print(f"{'='*55}\n")

    with open("logs/scheduler.log","a") as f:
        f.write(f"\n[{ts}]\n")
        for label,ok in results:
            f.write(f"  {'OK' if ok else 'FAIL'}  {label}\n")

    print(f"📄 Daily report: output/job_report_{datetime.now().strftime('%Y%m%d')}.html")
    print("🌐 Dashboard: python -m streamlit run dashboard.py")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--now",      action="store_true")
    parser.add_argument("--interval", type=int, default=24)
    args = parser.parse_args()
    pipeline()
    if args.now:
        print("Done!")
        return
    print(f"\n⏰ Next run in {args.interval} hours. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(args.interval * 3600)
            pipeline()
    except KeyboardInterrupt:
        print("\n👋 Scheduler stopped.")

if __name__ == "__main__":
    main()
