"""
Per-company scraper health tracking.

Reads this run's output/company_run_stats.json, appends it to the rolling
history in data/company_health.json (kept in git), and flags companies whose
scraper looks broken:

  FAILING   fetch failed in the last 2 consecutive runs
  ZERO      0 jobs in the last 2 consecutive runs, although it used to have jobs
  DROP      this run returned < 20% of its recent median (median >= 10)
  SLOW      fetch took longer than 240 s

Writes output/health_report.md (also shown in the Actions run summary) and
exits 0 always -- alerting is done by the workflow from the report.
"""

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

STATS = Path("output/company_run_stats.json")
HISTORY = Path("data/company_health.json")
REPORT = Path("output/health_report.md")
KEEP_RUNS = 14


def evaluate(history: dict) -> list:
    alerts = []
    for company, runs in sorted(history.items()):
        if not runs:
            continue
        last = runs[-1]
        prev_ok_counts = [r["count"] for r in runs[:-1] if r["ok"]][-7:]
        median = statistics.median(prev_ok_counts) if prev_ok_counts else None
        if len(runs) >= 2 and not runs[-1]["ok"] and not runs[-2]["ok"]:
            alerts.append((company, "FAILING", f"failed 2 runs in a row: {last.get('error', '')[:160]}"))
        elif (len(runs) >= 2 and runs[-1]["ok"] and runs[-2]["ok"] and runs[-1]["count"] == 0
              and runs[-2]["count"] == 0 and any(r["count"] > 0 for r in runs[:-2])):
            alerts.append((company, "ZERO", "0 jobs in 2 consecutive runs (previously had jobs)"))
        elif last["ok"] and median and median >= 10 and last["count"] < 0.2 * median:
            alerts.append((company, "DROP", f"{last['count']} jobs vs recent median {median:g}"))
        if last.get("seconds", 0) > 240:
            alerts.append((company, "SLOW", f"took {last['seconds']:.0f}s"))
    return alerts


def main():
    if not STATS.exists():
        print("no company_run_stats.json -- pipeline did not run; skipping health check")
        return 0
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else {}
    now = datetime.now(timezone.utc).isoformat(timespec="minutes")
    for company, s in stats.items():
        runs = history.setdefault(company, [])
        runs.append({"at": now, "ok": s["ok"], "count": s["count"], "seconds": s["seconds"],
                     **({"error": s["error"]} if s.get("error") else {})})
        history[company] = runs[-KEEP_RUNS:]
    HISTORY.parent.mkdir(exist_ok=True)
    HISTORY.write_text(json.dumps(history, indent=1, sort_keys=True), encoding="utf-8")

    alerts = evaluate(history)
    ok = sum(1 for s in stats.values() if s["ok"])
    total_jobs = sum(s["count"] for s in stats.values())
    lines = [f"## Company scraper health ({now})", "",
             f"{ok}/{len(stats)} companies fetched successfully, {total_jobs} jobs in total.", ""]
    if alerts:
        lines += ["| Company | Alert | Detail |", "|---|---|---|"]
        lines += [f"| {c} | {kind} | {detail.replace('|', '/')} |" for c, kind, detail in alerts]
    else:
        lines.append("No alerts.")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    Path("output/health_alert_count").write_text(str(sum(1 for a in alerts if a[1] != "SLOW")))
    return 0


def selftest():
    def run(ok, count, err=None):
        r = {"ok": ok, "count": count, "seconds": 5}
        if err:
            r["error"] = err
        return r
    h = {
        "Good": [run(True, 50)] * 5,
        "Broken": [run(True, 50), run(False, 0, "HTTP 500"), run(False, 0, "HTTP 500")],
        "Emptied": [run(True, 40), run(True, 0), run(True, 0)],
        "Dropped": [run(True, 100)] * 5 + [run(True, 5)],
        "OneFail": [run(True, 30), run(False, 0, "timeout")],
    }
    kinds = {(c, k) for c, k, _ in evaluate(h)}
    assert kinds == {("Broken", "FAILING"), ("Emptied", "ZERO"), ("Dropped", "DROP")}, kinds
    print("company_health self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        sys.exit(main())
