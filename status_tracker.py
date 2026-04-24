import argparse
from datetime import datetime

from helpers import export_tracker
from db import fetch_jobs, get_connection


def create_tracker(status=None, source_group=None):
    jobs = fetch_jobs(status=status, source_group=source_group)
    export_tracker(jobs)
    print(f"Tracker updated with {len(jobs)} jobs.")


def update_job_status(job_id, status, notes=""):
    timestamp = datetime.now().strftime("%Y-%m-%d")
    applied_date = timestamp if status == "Applied" else ""
    interview_date = timestamp if status == "Interview" else ""
    follow_up_date = timestamp if status == "Follow Up" else ""

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, notes = COALESCE(NULLIF(?, ''), notes),
                applied_date = CASE WHEN ? != '' THEN ? ELSE applied_date END,
                interview_date = CASE WHEN ? != '' THEN ? ELSE interview_date END,
                follow_up_date = CASE WHEN ? != '' THEN ? ELSE follow_up_date END
            WHERE job_id = ?
            """,
            (
                status,
                notes,
                applied_date,
                applied_date,
                interview_date,
                interview_date,
                follow_up_date,
                follow_up_date,
                job_id,
            ),
        )
        conn.commit()
    print(f"Updated {job_id} -> {status}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply tracker utilities")
    parser.add_argument("--status", help="Filter tracker by status")
    parser.add_argument("--source", help="Filter tracker by source group")
    parser.add_argument("--job-id", help="Job ID to update")
    parser.add_argument("--set-status", help="New status for the given job ID")
    parser.add_argument("--notes", default="", help="Optional notes while updating a job")
    args = parser.parse_args()

    if args.job_id and args.set_status:
        update_job_status(args.job_id, args.set_status, notes=args.notes)
    else:
        create_tracker(status=args.status, source_group=args.source)
