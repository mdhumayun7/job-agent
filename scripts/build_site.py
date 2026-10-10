"""
Assemble the deployable site in _site/.

  _site/index.html               landing page that forwards to the app
  _site/site/                    the single-page app (copied from site/)
  _site/site/js/config.js        written from SUPABASE_URL / SUPABASE_ANON_KEY
  _site/website-data/            data files the app reads
  _site/govt/index.html          crawlable list of government recruitments
  _site/govt/<id>/index.html     crawlable page per recruitment (meta tags, JSON-LD)
  _site/sitemap.xml, robots.txt

The app uses hash routes, which search engines do not index, so each government
recruitment also gets a small static page that summarises the official notice
and links into the app. Structured data (schema.org JobPosting) is only emitted
for records that were checked against the official notice and are still open or
upcoming, so search engines are never sent unverified or expired postings.

Usage: python scripts/build_site.py [--out _site]
Env:   SITE_URL (default https://mdhumayun7.github.io/job-agent),
       SUPABASE_URL, SUPABASE_ANON_KEY (optional, public values only)
"""

import argparse
import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = (os.getenv("SITE_URL") or "https://mdhumayun7.github.io/job-agent").rstrip("/")
NAME = "Job Agent"
DISCLAIMER = ("Job Agent is an independent student project. It is not affiliated with any government body, "
              "recruitment board or company. Always read the official notice before applying.")

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)  # noqa: E731


def fmt(d):
    if not d:
        return "Not recorded"
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return e(d)


def safe_url(u):
    return u if isinstance(u, str) and re.match(r"^https?://", u) else None


def write_config(out_js):
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_ANON_KEY", "").strip()
    if url and not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.(co|in)", url.rstrip("/")):
        print(f"SUPABASE_URL does not look like a Supabase project URL, ignoring it: {url!r}")
        url = ""
    if key and not re.fullmatch(r"[A-Za-z0-9._-]{20,4000}", key):
        print("SUPABASE_ANON_KEY has unexpected characters, ignoring it")
        key = ""
    if bool(url) != bool(key):
        print("Only one of SUPABASE_URL / SUPABASE_ANON_KEY is set; accounts stay disabled")
        url = key = ""
    out_js.write_text(
        "// Written by scripts/build_site.py from repository variables. Public values only.\n"
        f"export const SUPABASE_URL = {json.dumps(url.rstrip('/'))};\n"
        f"export const SUPABASE_ANON_KEY = {json.dumps(key)};\n", encoding="utf-8")
    print(f"config.js: accounts {'enabled' if url else 'disabled (device storage only)'}")


def page(title, description, canonical, body, extra_head="", depth=2):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{e(canonical)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="{NAME}">
<meta name="theme-color" content="#1d3a6e">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="{up}site/assets/app.css">
{extra_head}</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="site-header"><div class="header-inner">
  <a class="brand" href="{up}site/"><span class="brand-mark" aria-hidden="true">JA</span><span>{NAME}</span></a>
  <nav class="primary-nav" aria-label="Main"><a href="{up}site/#/govt">Government jobs</a><a href="{up}site/#/jobs">Company jobs</a><a href="{up}govt/">All recruitments</a></nav>
</div></header>
<main id="main"><div class="page" style="max-width:860px">
{body}
</div></main>
<footer class="site-footer"><div class="page small muted">{e(DISCLAIMER)}</div></footer>
</body>
</html>
"""


STATUS_LABEL = {"open": "Applications open", "upcoming": "Upcoming", "closed": "Closed", "unknown": "Dates not announced"}


def job_description(j):
    parts = [f"{j.get('organization')}: {j.get('title')}."]
    v = (j.get("vacancies") or {}).get("total")
    if v:
        parts.append(f"{v} vacancies{' (tentative)' if (j.get('vacancies') or {}).get('tentative') else ''}.")
    end = (j.get("dates") or {}).get("application_end")
    if end:
        parts.append(f"Last date to apply {fmt(end)}.")
    q = (j.get("qualification") or {}).get("notes")
    if q:
        parts.append(q)
    return " ".join(parts)[:300]


def job_jsonld(j):
    ver = (j.get("verification") or {}).get("status")
    dates = j.get("dates") or {}
    if ver != "verified" or j.get("status") not in ("open", "upcoming") or not dates.get("application_end"):
        return None
    posted = j.get("notice_date") or dates.get("application_start")
    if not posted:
        return None
    desc_html = "".join(f"<p>{e(x)}</p>" for x in [
        job_description(j), j.get("pay"), (j.get("age") or {}).get("note"),
        "Selection: " + "; ".join(j.get("selection_process") or []) if j.get("selection_process") else None,
        DISCLAIMER] if x)
    data = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": j.get("short_title") or j.get("title"),
        "description": desc_html,
        "identifier": {"@type": "PropertyValue", "name": j.get("org_short") or j.get("organization"),
                       "value": j.get("notification_no") or j["id"]},
        "datePosted": posted,
        "validThrough": dates["application_end"] + "T23:59:00+05:30",
        "employmentType": "FULL_TIME" if (j.get("employment_type") or "").lower() in ("permanent", "full time", "regular") else "OTHER",
        "hiringOrganization": {"@type": "Organization", "name": j.get("organization"),
                               "sameAs": safe_url((j.get("source") or {}).get("url"))},
        "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressCountry": "IN",
                                                      **({"addressRegion": j["state"]} if j.get("state") else {})}},
        "url": f"{SITE_URL}/govt/{j['id']}/",
    }
    total = (j.get("vacancies") or {}).get("total")
    if total:
        data["totalJobOpenings"] = total
    return data


def breadcrumb_ld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}


def ld_script(obj):
    # "</" must not appear inside a script element.
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"


def job_page(j):
    url = f"{SITE_URL}/govt/{j['id']}/"
    d = j.get("dates") or {}
    ver = j.get("verification") or {}
    links = j.get("links") or {}
    rows = [("Application starts", d.get("application_start")), ("Last date to apply", d.get("application_end")),
            ("Fee payment ends", d.get("fee_end")), ("Exam", d.get("exam"))]
    rows = [(k, v) for k, v in rows if v]
    v = j.get("vacancies") or {}
    fee = j.get("fee") or {}
    official = [(lbl, safe_url(u)) for lbl, u in [("Official notification", links.get("notification_pdf")),
                                                  ("Official application site", links.get("apply")),
                                                  ("Source page", (j.get("source") or {}).get("url"))]]
    official = [(lbl, u) for lbl, u in official if u]
    verified_line = (f"Checked against the official notice on {fmt(ver.get('checked_on'))}." if ver.get("status") == "verified"
                     else "Collected automatically from an official page and awaiting verification: eligibility and fees have not been reviewed.")
    body = f"""<nav class="breadcrumb" aria-label="Breadcrumb"><ol><li><a href="../../site/">Home</a></li><li><a href="../">Government recruitments</a></li><li aria-current="page">{e(j.get('short_title') or j.get('title'))}</li></ol></nav>
<div class="page-head"><h1>{e(j.get('title'))}</h1>
<p>{e(j.get('organization'))}{' &middot; ' + e(j.get('notification_no')) if j.get('notification_no') else ''}</p></div>
<p><span class="tag">{e(STATUS_LABEL.get(j.get('status'), 'Status unknown'))}</span> <span class="tag">{e(j.get('category'))}</span></p>
<p class="small muted">{e(verified_line)}</p>
<section class="panel"><h2>Important dates</h2>
{('<table class="kv"><tbody>' + ''.join(f'<tr><th scope="row">{e(k)}</th><td>{fmt(v2)}</td></tr>' for k, v2 in rows) + '</tbody></table>') if rows else '<p class="muted">Dates have not been announced in the official notice yet.</p>'}
{f'<p class="small muted">{e(d.get("exam_note"))}</p>' if d.get('exam_note') else ''}</section>
<section class="panel"><h2>Posts and vacancies</h2>
{('<ul>' + ''.join(f'<li>{e(p)}</li>' for p in j.get('posts') or []) + '</ul>') if j.get('posts') else ''}
<p>{f"{e(v.get('total'))} vacancies{' (tentative)' if v.get('tentative') else ''}." if v.get('total') else 'Vacancies: not recorded.'} {e(v.get('note') or '')}</p>
{f'<p>Pay: {e(j.get("pay"))}</p>' if j.get('pay') else ''}</section>
<section class="panel"><h2>Eligibility in brief</h2>
<p>{e((j.get('qualification') or {}).get('notes') or 'Education rule not recorded.')}</p>
<p>{e((j.get('age') or {}).get('note') or '')}</p>
{f'<p>Fee: Rs {e(fee.get("amount"))}{". Exempt: " + e(", ".join(fee.get("exempt") or [])) if fee.get("exempt") else ""}.</p>' if fee.get('amount') is not None else ''}
<p><a class="btn btn-primary" href="../../site/#/govt/{e(j['id'])}">Check your eligibility</a></p></section>
{('<section class="panel"><h2>Official links</h2><ul>' + ''.join(f'<li><a href="{e(u)}" rel="noopener noreferrer">{e(lbl)}</a></li>' for lbl, u in official) + '</ul></section>') if official else ''}
"""
    head = ld_script(breadcrumb_ld([("Home", f"{SITE_URL}/site/"), ("Government recruitments", f"{SITE_URL}/govt/"),
                                    (j.get("short_title") or j.get("title"), url)]))
    ld = job_jsonld(j)
    if ld:
        head += ld_script(ld)
    if j.get("status") == "closed":
        head += '<meta name="robots" content="noindex, follow">\n'
    title = f"{j.get('short_title') or j.get('title')}: dates, eligibility and official links | {NAME}"
    return page(title, job_description(j), url, body, head)


def index_page(jobs):
    order = {"open": 0, "upcoming": 1, "unknown": 2, "closed": 3}
    jobs = sorted(jobs, key=lambda j: (order.get(j.get("status"), 9), (j.get("dates") or {}).get("application_end") or "9999"))
    items = "".join(
        f'<li class="notice"><div><h3><a href="{e(j["id"])}/">{e(j.get("short_title") or j.get("title"))}</a></h3>'
        f'<div class="meta">{e(j.get("organization"))} &middot; {e(STATUS_LABEL.get(j.get("status"), ""))}'
        f'{" &middot; last date " + fmt((j.get("dates") or {}).get("application_end")) if (j.get("dates") or {}).get("application_end") else ""}</div></div></li>'
        for j in jobs)
    body = f"""<nav class="breadcrumb" aria-label="Breadcrumb"><ol><li><a href="../site/">Home</a></li><li aria-current="page">Government recruitments</li></ol></nav>
<div class="page-head"><h1>Government recruitments</h1><p>Each listing is read from the official notice or the organisation's official recruitment page. Open the app to filter, save jobs and check your eligibility.</p></div>
<p><a class="btn btn-primary" href="../site/#/govt">Open the government jobs list</a></p>
<ul class="notice-list">{items}</ul>"""
    return page(f"Government recruitments from official notices | {NAME}",
                "Government recruitment notices with dates, eligibility and official links, read from official sources.",
                f"{SITE_URL}/govt/", body, depth=1)


def landing():
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{NAME}: government and company jobs for students</title>
<meta name="description" content="Government recruitments read from official notices and CSE / IT openings from company career sites, with eligibility checks.">
<link rel="canonical" href="{SITE_URL}/site/">
<meta http-equiv="refresh" content="0; url=site/">
</head><body><p><a href="site/">Open {NAME}</a> or browse <a href="govt/">government recruitments</a>.</p></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site")
    args = ap.parse_args()
    out = ROOT / args.out
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "site", out / "site", ignore=shutil.ignore_patterns("__pycache__", "*.map"))
    write_config(out / "site" / "js" / "config.js")
    data_dir = ROOT / "website-data"
    if not data_dir.exists():
        sys.exit("website-data/ is missing: run generate_website_data.py and scripts/build_govt_data.py first")
    shutil.copytree(data_dir, out / "website-data")

    govt_file = data_dir / "govt.json"
    jobs = json.loads(govt_file.read_text(encoding="utf-8"))["jobs"] if govt_file.exists() else []
    (out / "govt").mkdir(parents=True, exist_ok=True)
    (out / "govt" / "index.html").write_text(index_page(jobs), encoding="utf-8")
    with_ld = 0
    for j in jobs:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", j.get("id", "")):
            print(f"skipping page for unsafe id {j.get('id')!r}")
            continue
        p = out / "govt" / j["id"]
        p.mkdir(parents=True, exist_ok=True)
        (p / "index.html").write_text(job_page(j), encoding="utf-8")
        with_ld += job_jsonld(j) is not None

    today = date.today().isoformat()
    urls = [(f"{SITE_URL}/site/", today), (f"{SITE_URL}/govt/", today)]
    urls += [(f"{SITE_URL}/govt/{j['id']}/", ((j.get("verification") or {}).get("checked_on") or today)[:10])
             for j in jobs if j.get("status") != "closed" and re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", j.get("id", ""))]
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{e(u)}</loc><lastmod>{m}</lastmod></url>\n" for u, m in urls) + "</urlset>\n", encoding="utf-8")
    base = urlparse(SITE_URL).path.rstrip("/") + "/"
    # Crawlers only read robots.txt at the domain root; on a project Pages site
    # (user.github.io/repo/) this file is informational and the sitemap must be
    # submitted in Search Console instead. With a custom domain it works as is.
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: {base}website-data/\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (out / "index.html").write_text(landing(), encoding="utf-8")
    (out / ".nojekyll").touch()
    (out / "404.html").write_text(page(f"Page not found | {NAME}", "This page does not exist.", f"{SITE_URL}/",
                                       f'<h1>This page does not exist</h1><p><a href="{e(base)}site/">Open {NAME}</a></p>', depth=0)
                                  .replace('href="site/', f'href="{base}site/').replace('href="govt/', f'href="{base}govt/'), encoding="utf-8")
    print(f"built {out.relative_to(ROOT)}: {len(jobs)} govt pages ({with_ld} with JobPosting data), {len(urls)} sitemap URLs, "
          f"generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
