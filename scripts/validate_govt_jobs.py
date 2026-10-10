"""
Validate data/govt_jobs.json. Exit 1 on errors (CI blocks the change), print
warnings. Usage: python scripts/validate_govt_jobs.py [path]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from govt_schema import validate_all  # noqa: E402


def main(path="data/govt_jobs.json"):
    jobs = json.loads(Path(path).read_text(encoding="utf-8"))["jobs"]
    errors, warnings = validate_all(jobs)
    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("error:", e)
    print(f"{len(jobs)} records, {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
