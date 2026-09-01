import json
from pathlib import Path
from datetime import datetime
from config import ENRICHED_OUTPUT_FILE, JOBS_FILE, PERSONAL_INFO

def load_jobs():
    src = Path(ENRICHED_OUTPUT_FILE) if Path(ENRICHED_OUTPUT_FILE).exists() else Path(JOBS_FILE)
    with open(src,"r",encoding="utf-8") as f: return json.load(f)

def generate_pdf_report(top_n=20):
    jobs = load_jobs()
    top = sorted(jobs, key=lambda j: j.get("ai_match_score",j.get("match_score",0)), reverse=True)[:top_n]
    name = PERSONAL_INFO.get("name","Candidate")
    today = datetime.now().strftime("%d %B %Y")
    out_path = f"output/job_report_{datetime.now().strftime('%Y%m%d')}.html"

    score_color = lambda s: "#22c55e" if s>=60 else ("#6366f1" if s>=40 else ("#f59e0b" if s>=20 else "#ef4444"))

    cards = ""
    for i, job in enumerate(top, 1):
        sc = job.get("ai_match_score", job.get("match_score",0))
        matched = ", ".join(job.get("matched_skills",[])[:5])
        missing = ", ".join(job.get("missing_skills",[])[:3])
        cover = job.get("cover_letter_opening","")
        fit = job.get("fit_reason","")
        col = score_color(sc)
        cards += f"""
        <div class="job-card">
            <div class="job-header">
                <div class="job-info">
                    <div class="job-num">#{i}</div>
                    <div>
                        <div class="job-title">{job.get('title','')}</div>
                        <div class="job-meta">{job.get('company','')} · {job.get('location','')} · {job.get('source_group',job.get('source',''))}</div>
                    </div>
                </div>
                <div class="score-badge" style="background:{col}22;color:{col};border:2px solid {col}">{sc}</div>
            </div>
            {'<div class="fit-reason">💡 '+fit+'</div>' if fit else ''}
            {'<div class="skills-matched">✅ Matched: '+matched+'</div>' if matched else ''}
            {'<div class="skills-missing">⚠️ Missing: '+missing+'</div>' if missing else ''}
            {'<div class="cover-letter">✍️ '+cover+'</div>' if cover else ''}
            <div class="job-footer">
                <span class="salary">💰 {job.get('salary','Not mentioned')}</span>
                {'<a href="'+job.get('apply_url','')+'" class="apply-btn">Apply Now →</a>' if job.get('apply_url') else ''}
            </div>
        </div>"""

    from collections import Counter
    sources = Counter(j.get("source_group",j.get("source","")) for j in jobs)
    src_rows = "".join([f"<tr><td>{s}</td><td><b>{c}</b></td></tr>" for s,c in sources.most_common()])
    score_dist = {"60-100":0,"40-59":0,"20-39":0,"0-19":0}
    for j in jobs:
        s=j.get("ai_match_score",j.get("match_score",0))
        if s>=60: score_dist["60-100"]+=1
        elif s>=40: score_dist["40-59"]+=1
        elif s>=20: score_dist["20-39"]+=1
        else: score_dist["0-19"]+=1

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Job Report - {today}</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * {{ margin:0;padding:0;box-sizing:border-box;font-family:'Inter',sans-serif; }}
    body {{ background:#050816;color:#e2e8f0;padding:30px; }}
    .header {{ background:linear-gradient(135deg,#4f46e5,#7c3aed);border-radius:16px;padding:30px;margin-bottom:30px;text-align:center; }}
    .header h1 {{ font-size:2rem;font-weight:800;color:white; }}
    .header p {{ color:#c7d2fe;margin-top:8px; }}
    .stats {{ display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:30px; }}
    .stat-card {{ background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);border-radius:12px;padding:20px;text-align:center; }}
    .stat-num {{ font-size:2rem;font-weight:800;color:#818cf8; }}
    .stat-label {{ color:#64748b;font-size:0.85rem;margin-top:4px; }}
    .section-title {{ font-size:1.2rem;font-weight:700;border-left:4px solid #6366f1;padding-left:12px;margin:24px 0 16px; }}
    .job-card {{ background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:16px; }}
    .job-header {{ display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px; }}
    .job-info {{ display:flex;gap:12px;align-items:flex-start; }}
    .job-num {{ background:#6366f1;color:white;font-weight:800;width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0; }}
    .job-title {{ font-size:1rem;font-weight:700;color:#e2e8f0; }}
    .job-meta {{ color:#64748b;font-size:0.85rem;margin-top:3px; }}
    .score-badge {{ font-size:1.2rem;font-weight:900;padding:6px 14px;border-radius:10px;flex-shrink:0; }}
    .fit-reason {{ color:#94a3b8;font-size:0.85rem;font-style:italic;margin:8px 0;padding:8px 12px;background:rgba(99,102,241,0.08);border-radius:8px; }}
    .skills-matched {{ color:#22c55e;font-size:0.82rem;margin:6px 0; }}
    .skills-missing {{ color:#f59e0b;font-size:0.82rem;margin:6px 0; }}
    .cover-letter {{ color:#c7d2fe;font-size:0.85rem;font-style:italic;margin-top:8px;padding:10px 14px;background:rgba(99,102,241,0.1);border-radius:8px;border-left:3px solid #6366f1; }}
    .job-footer {{ display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid #334155; }}
    .salary {{ color:#64748b;font-size:0.82rem; }}
    .apply-btn {{ background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:7px 18px;border-radius:8px;text-decoration:none;font-size:0.85rem;font-weight:600; }}
    table {{ width:100%;border-collapse:collapse;margin-bottom:20px; }}
    th {{ background:#1e293b;color:#94a3b8;padding:10px;text-align:left;font-size:0.85rem; }}
    td {{ padding:10px;border-bottom:1px solid #1e293b;font-size:0.9rem;color:#e2e8f0; }}
    tr:hover td {{ background:rgba(99,102,241,0.05); }}
    .footer {{ text-align:center;color:#334155;font-size:0.8rem;margin-top:30px;padding-top:20px;border-top:1px solid #1e293b; }}
    @media print {{ body{{background:white;color:black}} .job-card{{border:1px solid #ccc}} }}
</style>
</head><body>
<div class="header">
    <h1>🚀 Job Search Report</h1>
    <p>{name} · {today} · Top {top_n} Matches</p>
</div>
<div class="stats">
    <div class="stat-card"><div class="stat-num">{len(jobs)}</div><div class="stat-label">Total Jobs Found</div></div>
    <div class="stat-card"><div class="stat-num">{score_dist['60-100']}</div><div class="stat-label">Excellent Matches</div></div>
    <div class="stat-card"><div class="stat-num">{score_dist['40-59']}</div><div class="stat-label">Good Matches</div></div>
    <div class="stat-card"><div class="stat-num">{len(sources)}</div><div class="stat-label">Platforms Scraped</div></div>
</div>
<div class="section-title">📡 Platform Breakdown</div>
<table><tr><th>Platform</th><th>Jobs Found</th></tr>{src_rows}</table>
<div class="section-title">🏆 Top {top_n} Job Matches</div>
{cards}
<div class="footer">Generated by Job Agent Pro · {today}</div>
</body></html>"""

    Path(out_path).parent.mkdir(exist_ok=True)
    with open(out_path,"w",encoding="utf-8") as f: f.write(html)
    print(f"✅ Report saved: {out_path}")
    print(f"   Open in browser and Ctrl+P to save as PDF")
    return out_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    generate_pdf_report(top_n=args.top)
