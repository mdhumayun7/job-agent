"""
Telegram alerts for newly discovered high-match jobs.

Sends every job that is NEW in this run and is a top match (score at or above
the profile threshold), plus new government / research notices, to a Telegram
chat. Each job is alerted once, because NEW is relative to the previous run.

Setup (one time):
  1. In Telegram, talk to @BotFather -> /newbot -> copy the bot token.
  2. Send any message to your new bot, then open
     https://api.telegram.org/bot<TOKEN>/getUpdates and copy "chat":{"id": ...}.
  3. Add repository secrets TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
Without the secrets this script does nothing and exits 0.
"""

import html
import json
import os
import sys
import time
from pathlib import Path

import requests

MAX_JOBS = 25
LIMIT = 3900  # Telegram max message length is 4096


def pick_jobs():
    top = json.loads(Path("output/top_matches.json").read_text(encoding="utf-8")) \
        if Path("output/top_matches.json").exists() else []
    allj = json.loads(Path("output/ats_jobs.json").read_text(encoding="utf-8")) \
        if Path("output/ats_jobs.json").exists() else []
    new_top = [j for j in top if j.get("status") == "NEW"]
    govt = [j for j in allj if j.get("status") == "NEW" and j.get("source_type") == "govt_notice"]
    return new_top[:MAX_JOBS], govt[:10]


def fmt(j):
    title = html.escape(j.get("job_title") or "")
    company = html.escape(j.get("company") or "")
    loc = html.escape(j.get("location_raw") or "")
    url = j.get("apply_url") or j.get("job_url") or ""
    score = j.get("match_score")
    head = f"<b>{title}</b>\n{company} · {loc}"
    if score:
        head += f"\nMatch {score}/100"
    if j.get("application_deadline"):
        head += f" · Last date {html.escape(str(j['application_deadline']))}"
    if url.startswith("http"):
        head += f'\n<a href="{html.escape(url, quote=True)}">Apply</a>'
    return head


def chunks(blocks):
    msg = ""
    for b in blocks:
        if len(msg) + len(b) + 2 > LIMIT:
            yield msg
            msg = ""
        msg += b + "\n\n"
    if msg.strip():
        yield msg


def send(token, chat_id, text):
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=20, json={
        "chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})
    if r.status_code != 200:
        raise RuntimeError(f"Telegram API {r.status_code}: {r.text[:200]}")


def main():
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing) -- skipping.")
        return 0
    jobs, govt = pick_jobs()
    if not jobs and not govt:
        print("No new top matches or notices this run -- nothing to send.")
        return 0
    blocks = []
    if jobs:
        blocks.append(f"<b>{len(jobs)} new top-matching job(s)</b>")
        blocks += [fmt(j) for j in jobs]
    if govt:
        blocks.append(f"<b>{len(govt)} new government / research notice(s)</b>")
        blocks += [fmt(j) for j in govt]
    for text in chunks(blocks):
        send(token, chat_id, text)
        time.sleep(1)
    print(f"Telegram: sent {len(jobs)} jobs and {len(govt)} notices.")
    return 0


def selftest():
    j = {"job_title": "SDE <Intern>", "company": "A&B", "location_raw": "Pune", "match_score": 80,
         "apply_url": "https://x/y?a=1&b=2"}
    out = fmt(j)
    assert "SDE &lt;Intern&gt;" in out and "A&amp;B" in out and 'href="https://x/y?a=1&amp;b=2"' in out, out
    assert "href" not in fmt({**j, "apply_url": "javascript:alert(1)"})
    parts = list(chunks(["x" * 2000, "y" * 2000, "z" * 100]))
    assert len(parts) == 2 and all(len(p) <= 4096 for p in parts), [len(p) for p in parts]
    print("telegram_alert self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        sys.exit(main())
