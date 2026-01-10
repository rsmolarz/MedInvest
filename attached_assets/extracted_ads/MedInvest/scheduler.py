"""Simple scheduler for ops jobs.

Usage:
  python scheduler.py

This uses a basic loop to avoid extra dependencies.
Intervals:
- SLA monitor: every 15 minutes
- Invite boosts: daily
- Weekly digest: weekly

Configure:
- SLA_HOURS_THRESHOLD (default 72)
- OPS_ADMIN_EMAILS (comma-separated)
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from ops_jobs import monitor_verification_sla_and_alert, auto_route_verification_queue, invite_credit_boosts_by_specialty, weekly_signal_digest


def main():
    last_sla = None
    last_invite = None
    last_digest = None

    while True:
        now = datetime.utcnow()

        if (not last_sla) or (now - last_sla) >= timedelta(minutes=15):
            res = monitor_verification_sla_and_alert()
            if res.get('breached'):
                auto_route_verification_queue()
            last_sla = now

        if (not last_invite) or (now.date() != last_invite.date()):
            invite_credit_boosts_by_specialty()
            last_invite = now

        # Run digest on Mondays at 12:00 UTC (weekly cadence)
        if now.weekday() == 0 and now.hour == 12:
            if (not last_digest) or (now - last_digest) >= timedelta(days=6):
                weekly_signal_digest()
                last_digest = now

        time.sleep(30)


if __name__ == '__main__':
    main()
