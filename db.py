import json
import sqlite3
from pathlib import Path

from config import DB_FILE


def get_connection():
    Path(DB_FILE).parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_FILE)


def fetch_jobs(status=None, source_group=None):
    query = "SELECT raw_json FROM jobs"
    params = []
    clauses = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if source_group:
        clauses.append("source_group = ?")
        params.append(source_group)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY match_score DESC, scraped_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [json.loads(row[0]) for row in rows]
