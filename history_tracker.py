import json
from datetime import datetime
from pathlib import Path

HISTORY_FILE = "data/score_history.json"

def load_history():
    p = Path(HISTORY_FILE)
    if not p.exists(): return []
    with open(p) as f: return json.load(f)

def save_today(jobs):
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    # Remove existing entry for today
    history = [h for h in history if h.get("date") != today]
    scores = [j.get("ai_match_score", j.get("match_score", 0)) for j in jobs]
    history.append({
        "date": today,
        "total": len(jobs),
        "avg_score": round(sum(scores)/max(1,len(scores)), 1),
        "excellent": sum(1 for s in scores if s >= 60),
        "good": sum(1 for s in scores if 40 <= s < 60),
        "sources": {}
    })
    # Keep last 30 days
    history = sorted(history, key=lambda h: h["date"])[-30:]
    Path(HISTORY_FILE).parent.mkdir(exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    print(f"History saved for {today}")

if __name__ == "__main__":
    from config import ENRICHED_OUTPUT_FILE, JOBS_FILE
    src = Path(ENRICHED_OUTPUT_FILE) if Path(ENRICHED_OUTPUT_FILE).exists() else Path(JOBS_FILE)
    with open(src) as f: jobs = json.load(f)
    save_today(jobs)
