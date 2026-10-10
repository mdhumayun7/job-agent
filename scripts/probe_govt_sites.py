"""
Probe government / PSU / research-institute recruitment pages.
For each page records (a) whether the notices are in the static HTML
(plain requests) and (b) the rendered anchors with their row text, so a
reliable parser can be chosen per site. Output: probe_results.json
"""

import json
import re
import requests
from playwright.sync_api import sync_playwright

SITES = {
    "C-DAC (careers portal)": "https://careers.cdac.in/",
    "C-DAC (current jobs)": "https://www.cdac.in/index.aspx?id=current_jobs",
    "DRDO": "https://www.drdo.gov.in/drdo/careers",
    "DRDO (jobs)": "https://www.drdo.gov.in/jobs",
    "ISRO": "https://www.isro.gov.in/Careers.html",
    "BARC": "https://www.barc.gov.in/recruitment/",
    "BEL": "https://bel-india.in/job-notifications/",
    "BEL (recruitment)": "https://bel-india.in/recruitment/",
    "HAL": "https://hal-india.co.in/career",
    "ECIL": "https://www.ecil.co.in/jobs.html",
    "NPCIL": "https://www.npcilcareers.co.in/",
    "NIELIT": "https://www.nielit.gov.in/recruitments",
    "NIC": "https://www.nic.in/recruitment/",
    "C-DOT": "https://www.cdot.in/cdotweb/web/career.php",
    "STPI": "https://stpi.in/en/careers",
    "IISc": "https://iisc.ac.in/careers/",
    "IIT Bombay (IRCC project posts)": "https://rnd.iitb.ac.in/jobs",
    "IIT Madras (ICSR project posts)": "https://icsrstaff.iitm.ac.in/careers/current_openings.php",
    "IIT Delhi (project posts)": "https://ird.iitd.ac.in/current-openings",
    "SVNIT Surat": "https://www.svnit.ac.in/web/recruitment.php",
}

KEYWORDS = re.compile(r"recruit|vacanc|advertis|advt|notification|project (engineer|associate|scientist|assistant)|"
                      r"jrf|srf|research (associate|fellow)|scientist|engineer|walk[- ]?in|apply|post of|career", re.I)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

JS = """() => [...document.querySelectorAll('a')].map(a => {
  const row = a.closest('tr, li, p, .row, article, div');
  return {text: (a.innerText || '').trim().slice(0, 200), href: a.href,
          row: row ? (row.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 300) : ''};
})"""


def main():
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(user_agent=UA, ignore_https_errors=True)
        for name, url in SITES.items():
            rec = {"site": name, "url": url}
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=30, verify=False)
                rec["static_status"] = r.status_code
                rec["static_keyword_links"] = len([m for m in re.finditer(r"<a[^>]*>(.*?)</a>", r.text, re.S | re.I)
                                                   if KEYWORDS.search(m.group(1))])
            except Exception as e:  # noqa: BLE001
                rec["static_error"] = str(e)[:200]
            try:
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:  # noqa: BLE001
                    pass
                rec["final_url"] = page.url
                rec["title"] = page.title()[:120]
                anchors = page.evaluate(JS)
                hits = [a for a in anchors if a["text"] and (KEYWORDS.search(a["text"]) or KEYWORDS.search(a["href"] or ""))]
                rec["rendered_anchor_count"] = len(anchors)
                rec["keyword_anchors"] = hits[:60]
                page.close()
            except Exception as e:  # noqa: BLE001
                rec["render_error"] = str(e)[:200]
            print(name, rec.get("static_status"), rec.get("static_keyword_links"), len(rec.get("keyword_anchors", [])),
                  rec.get("static_error", "")[:80], rec.get("render_error", "")[:80], flush=True)
            out.append(rec)
        b.close()
    with open("probe_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()
