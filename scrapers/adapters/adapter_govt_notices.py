"""
Government / PSU / research-institute recruitment notices.

These organisations publish recruitment as a list of notices (often PDFs),
not as an ATS feed. Each source below is a page whose static HTML lists the
notices; a notice is kept only when its text looks like an opening
(advertisement, walk-in, "applications invited", project posts) and is not
a follow-up document (results, shortlists, admit cards, corrigenda, ...).

Every field comes from the notice text: the title is the notice text,
"last date" and "dated" dates are parsed only when written explicitly, and
the location is "India" (all sources are Indian public bodies) unless the
notice names a city.

verified_slug: a key of SOURCES, e.g. "cdac"
"""

import re
import sys
import time
import hashlib
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "config"))
from job_schema import Job  # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

OPENING_RE = re.compile(r"recruit|advertis|advt|walk[- ]?in|applications? (are )?invited|invites? (online )?applications|"
                        r"vacanc|project (staff|engineer|associate|assistant|scientist|manager)|jrf|srf|"
                        r"research (associate|fellow)|post of|positions?", re.I)
FOLLOWUP_RE = re.compile(r"result|select(ed|ion)? list|selected candidates?|list of (selected |shortlisted )?candidates|shortlist|admit card|hall ticket|corrigend|addend|withdraw|"
                         r"answer key|interview schedule|rejected|accepted|marks|merit list|minutes|tender|"
                         r"application form|notice regarding|extension of|cancell|postpone|document verification|"
                         r"provisional|waiting list|joining|instructions|syllabus|faq|career progression|read more",
                         re.I)

# Only sources whose static HTML was verified (scripts/probe_govt_sites.py)
# to list real openings are enabled. ISRO and IISc pages were probed but
# their static HTML yields navigation links / old exam notices, not openings.
SOURCES = {
    "cdac": {"org": "C-DAC", "urls": ["https://www.cdac.in/index.aspx?id=current_jobs"], "title_from": "row"},
}

DATE = r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9},?\s+\d{4})"
LAST_DATE_RE = re.compile(r"(last date|closing date|on or before|till|upto|up to)[^0-9]{0,60}" + DATE, re.I)
DATED_RE = re.compile(r"\bdated?\s*:?\s*" + DATE, re.I)
CITY_RE = re.compile(r"\b(Bengaluru|Bangalore|Pune|Hyderabad|Chennai|Mumbai|Noida|Delhi|Kolkata|Thiruvananthapuram|"
                     r"Trivandrum|Mohali|Patna|Guwahati|Silchar|Ahmedabad|Gandhinagar|Indore|Bhubaneswar|"
                     r"Sriharikota|Ahmedabad|Valiamala|Mahendragiri)\b", re.I)

BLOCK_TAGS = {"tr", "li", "p", "div", "td", "article", "section"}


class _Collector(HTMLParser):
    """Collects anchors together with the text of their innermost block."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []   # stack of [tag, text_parts]
        self.anchor = None
        self.anchors = []  # dicts: text, href, block (list ref)

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK_TAGS:
            self.blocks.append([tag, []])
        if tag == "a":
            self.anchor = {"text": [], "href": dict(attrs).get("href") or "",
                           "block": self.blocks[-1][1] if self.blocks else None}

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            self.anchor["text"] = " ".join("".join(self.anchor["text"]).split())
            self.anchors.append(self.anchor)
            self.anchor = None
        if tag in BLOCK_TAGS:
            for i in range(len(self.blocks) - 1, -1, -1):
                if self.blocks[i][0] == tag:
                    closed = self.blocks.pop(i)
                    if self.blocks:  # inner text also belongs to the parent block
                        self.blocks[-1][1].extend(closed[1])
                    break

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor["text"].append(data)
        if self.blocks:
            self.blocks[-1][1].append(data)


def _parse_date(text):
    text = re.sub(r"(st|nd|rd|th)\b", "", text.strip())
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%y", "%d/%m/%y", "%d %B %Y", "%d %b %Y",
                "%d %B, %Y", "%d %b, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def extract_notices(html: str, base_url: str, title_from: str = "row") -> list:
    c = _Collector()
    c.feed(html)
    notices, seen = [], set()
    for a in c.anchors:
        href = urljoin(base_url, a["href"]) if a["href"] and not a["href"].startswith(("javascript", "mailto", "#")) else ""
        row = " ".join("".join(a["block"] or []).split()) if a["block"] is not None else ""
        text = a["text"]
        title = (row if title_from == "row" and len(row) > len(text) else text)[:300]
        probe = f"{text} {row}" if title_from == "row" else text
        if not href or len(title) < 15 or not OPENING_RE.search(probe) or FOLLOWUP_RE.search(text):
            continue
        if FOLLOWUP_RE.search(title[:120]):
            continue
        key = title.lower()[:150]  # several documents (ad, form) can share one notice row
        if key in seen:
            continue
        seen.add(key)
        last = LAST_DATE_RE.search(row or text)
        dated = DATED_RE.search(row or text)
        city = CITY_RE.search(title)
        notices.append({"title": title, "url": href,
                        "last_date": _parse_date(last.group(2)) if last else None,
                        "dated": _parse_date(dated.group(1)) if dated else None,
                        "city": city.group(1).title() if city else None})
    return notices


def fetch_govt_notices(key: str, company_display_name: str) -> list:
    src = SOURCES[key]
    jobs, ok_pages = [], 0
    for url in src["urls"]:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        except requests.RequestException as e:
            print(f"[govt:{key}] {url} failed: {e}")
            continue
        if r.status_code != 200:
            print(f"[govt:{key}] {url} returned HTTP {r.status_code}")
            continue
        ok_pages += 1
        for n in extract_notices(r.text, url, src.get("title_from", "row")):
            nid = hashlib.sha1(n["url"].encode()).hexdigest()[:12]
            jobs.append(Job(
                company=company_display_name,
                job_title=n["title"],
                job_id=nid,
                job_url=n["url"], apply_url=n["url"],
                location_raw=f"{n['city']}, India" if n["city"] else "India",
                country="India",
                employment_type="Government / Institute notice",
                date_posted=n["dated"],
                application_deadline=n["last_date"],
                deadline_status="Open" if n["last_date"] else "Deadline Not Specified",
                job_description=n["title"],
                source_website=url,
                source_type="govt_notice",
                scraped_at=datetime.now(timezone.utc).isoformat(),
            ).to_dict())
        time.sleep(1)
    if ok_pages == 0:
        raise RuntimeError(f"govt source '{key}': no page could be fetched")
    print(f"[govt:{key}] {company_display_name}: {len(jobs)} notices")
    return jobs


def selftest():
    html = """<table>
    <tr><td><a href="/a.pdf">Walk-In Interview for Project Engineer posts at C-DAC Pune</a>
        (Advt. No. 12/2026 dated 01.10.2026) Last date: 20.10.2026</td></tr>
    <tr><td><a href="/b.pdf">Selected Candidate list for the post of Project Assistant</a></td></tr>
    <tr><td><a href="/c.pdf">Corrigendum - Advertisement 11/2026</a></td></tr>
    <tr><td><a href="#">Skip to main content</a></td></tr>
    </table>"""
    n = extract_notices(html, "https://www.cdac.in/x", "row")
    assert len(n) == 1, n
    assert n[0]["url"] == "https://www.cdac.in/a.pdf" and n[0]["last_date"] == "2026-10-20", n
    assert n[0]["dated"] == "2026-10-01" and n[0]["city"] == "Pune", n
    print("adapter_govt_notices self-test passed")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest":
        selftest()
    else:
        print(len(fetch_govt_notices(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])))
