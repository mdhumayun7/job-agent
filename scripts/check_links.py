"""
Check the official links on every government record (notification PDF, apply
site, source page, event links).

Writes output/link_checks.json, and when SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY are set, upserts the results into the link_checks
table so editors see broken links in the admin dashboard.

A link counts as working for any 2xx/3xx response. Some official sites refuse
HEAD or automated requests (403/405); those are retried with GET and, if still
refused, recorded with ok = false so an editor can confirm by hand.

Usage: python scripts/check_links.py [--input website-data/govt.json]
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobAgentLinkCheck/1.0; +https://github.com/mdhumayun7/job-agent)"}


def collect(jobs):
    seen = {}
    for j in jobs:
        links = j.get("links") or {}
        urls = [links.get("notification_pdf"), links.get("apply"), (j.get("source") or {}).get("url")]
        urls += [ev.get("url") for ev in j.get("events") or []]
        for u in urls:
            if isinstance(u, str) and re.match(r"^https?://", u) and u not in seen:
                seen[u] = j.get("id")
    return seen


def check(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code in (403, 405, 400, 501) or r.status_code >= 500:
            r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True, stream=True)
            r.close()
        return r.status_code, 200 <= r.status_code < 400
    except requests.RequestException as ex:
        print(f"  {url}: {type(ex).__name__}")
        return None, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(ROOT / "website-data" / "govt.json"))
    args = ap.parse_args()
    path = Path(args.input)
    if not path.exists():
        sys.exit(f"{path} not found")
    jobs = json.loads(path.read_text(encoding="utf-8"))["jobs"]
    urls = collect(jobs)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(lambda u: (u, *check(u)), urls))
    rows = [{"url": u, "job_id": urls[u], "status": st, "ok": ok, "checked_at": now} for u, st, ok in results]
    out = ROOT / "output" / "link_checks.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    bad = [r for r in rows if not r["ok"]]
    print(f"checked {len(rows)} links, {len(bad)} not reachable")
    for r in bad:
        print(f"  {r['status']} {r['url']} ({r['job_id']})")

    sb_url, key = os.getenv("SUPABASE_URL", "").rstrip("/"), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if sb_url and key and rows:
        r = requests.post(f"{sb_url}/rest/v1/link_checks?on_conflict=url", json=rows, timeout=30,
                          headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                   "Prefer": "resolution=merge-duplicates,return=minimal"})
        print(f"link_checks upsert: HTTP {r.status_code}")
        if r.status_code >= 300:
            print(r.text[:500])


if __name__ == "__main__":
    main()
