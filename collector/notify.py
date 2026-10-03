"""Email the strongest new matches.

Best-effort by design: a failure here is logged and swallowed. Notification is
a convenience, and it must never cost you a collection run that already spent
real Gemini quota. Only jobs scored in THIS run are sent, so you are never
emailed twice about the same posting.
"""
import html
import logging
import os

import requests

from . import config as C

log = logging.getLogger(__name__)
ENDPOINT = "https://api.resend.com/emails"


def available():
    return bool(os.environ.get("RESEND_API_KEY") and os.environ.get("NOTIFY_EMAIL"))


def pick(scored_now):
    """The ones worth interrupting someone for: highest first."""
    good = [(j, r) for j, r in scored_now if r.get("score", 0) >= C.NOTIFY_MIN_SCORE]
    return sorted(good, key=lambda pair: -pair[1]["score"])


def build(rows):
    """Returns (subject, html). Kept pure so it can be tested without network."""
    n = len(rows)
    top = rows[0][1]["score"]
    subject = (f"{n} new job match{'' if n == 1 else 'es'} "
               f"({top}/10 best) - Job Radar")
    items = []
    for job, res in rows:
        bullets = "".join(f"<li>{html.escape(b)}</li>" for b in (res.get("bullets") or []))
        items.append(
            f'<li style="margin-bottom:18px">'
            f'<b>{res["score"]}/10</b> &nbsp;'
            f'<a href="{html.escape(job["url"])}">{html.escape(job["title"])}</a><br>'
            f'{html.escape(job["company"])} &middot; {html.escape(job["location"])}'
            f'{" &middot; " + html.escape(job["salary"]) if job.get("salary") else ""}<br>'
            f'<i>{html.escape(res.get("reason", ""))}</i>'
            f'{f"<ul>{bullets}</ul>" if bullets else ""}'
            f'</li>')
    body = (f"<p>Scoring {C.NOTIFY_MIN_SCORE}+ against your profile, newest run:</p>"
            f"<ol>{''.join(items)}</ol>"
            f"<p style=\"color:#666;font-size:13px\">Sent by your own collector. "
            f"Change the threshold with NOTIFY_MIN_SCORE in collector/config.py.</p>")
    return subject, body


def send(scored_now, session=None):
    """Returns the number of jobs notified about; 0 if nothing to send or it failed."""
    rows = pick(scored_now)
    if not rows:
        return 0
    if not available():
        log.info("%d match(es) worth emailing, but RESEND_API_KEY / NOTIFY_EMAIL are not set", len(rows))
        return 0
    subject, body = build(rows)
    s = session or requests
    try:
        r = s.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
            json={"from": os.environ.get("NOTIFY_FROM", "onboarding@resend.dev"),
                  "to": [os.environ["NOTIFY_EMAIL"]],
                  "subject": subject,
                  "html": body},
            timeout=30,
        )
        if r.status_code >= 400:
            log.warning("email not sent (HTTP %s): %s", r.status_code, getattr(r, "text", "")[:200])
            return 0
    except Exception as e:  # noqa: BLE001 - never fail a run over a notification
        log.warning("email not sent (%s)", e)
        return 0
    log.info("emailed %d new match(es) to %s", len(rows), os.environ["NOTIFY_EMAIL"])
    return len(rows)
