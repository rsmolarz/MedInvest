"""Simple DB-backed worker for AI jobs.

Usage:
  python worker.py

Environment:
  DATABASE_URL - same as app
  OPENAI_API_KEY - enable OpenAI calls
"""

import time

from app import app
from ai_jobs import claim_next_job, process_job


def main(poll_seconds: float = 1.0):
    with app.app_context():
        pass

    while True:
        job = claim_next_job()
        if not job:
            time.sleep(poll_seconds)
            continue
        process_job(job.id)


if __name__ == "__main__":
    main()
