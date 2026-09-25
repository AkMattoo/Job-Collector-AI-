"""The scored-jobs store. A job counts as 'seen' only once it has a score.
Recording happens after scoring succeeds, never before, so failures are retried."""
import json
import os
from datetime import datetime, timedelta, timezone

from . import config as C
from .filters import freshness
from .normalize import days_since


def load(path=C.STORE_PATH):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(store, path=C.STORE_PATH):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=1, sort_keys=True)


def record(store, job, result, today):
    store[job["url"]] = {
        "score": result["score"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "duration": result.get("duration") or job["duration"],
        "salary": result.get("salary") or job["salary"],
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "salary_predicted": job.get("salary_predicted", False),
        "source": job.get("source", "board"),
        "posted": job["posted"],
        "open_roles_at_company": job["open_roles_at_company"],
        "why_it_fits": result.get("reason", ""),
        "tailored_bullets": result.get("bullets", [])[:3],
        "snippet": job["description"][:C.SNIPPET_CHARS],
        "url": job["url"],
        "found_on": today,
        "last_seen_open": today,
    }


def mark_open(store, live_urls, today):
    for url in live_urls & store.keys():
        store[url]["last_seen_open"] = today


def prune(store, now):
    cutoff = (now - timedelta(days=C.FORGET_AFTER_DAYS)).date().isoformat()
    for url in [u for u, v in store.items() if v.get("last_seen_open", v["found_on"]) < cutoff]:
        del store[url]


def _pay_rank(v):
    """2 = stated pay at or above target, 1 = stated but below, 0 = not stated."""
    top = v.get("salary_max") or v.get("salary_min")
    if not top:
        return 0
    return 2 if top >= C.SALARY_TARGET else 1


def publish(store, now, path=C.PUBLISH_PATH):
    today = now.date().isoformat()
    rows = []
    for v in store.values():
        if v["score"] < C.MIN_SCORE:
            continue
        days = days_since(v.get("posted"), now)
        rows.append({**v, "days_live": days, "freshness": freshness(days),
                     "still_open": v.get("last_seen_open") == today,
                     "pay_rank": _pay_rank(v)})
    # Rank: open first, then fit score, then pay (stated and at/above target
    # beats stated-but-lower, which beats unknown), then freshness.
    rows.sort(key=lambda r: (not r["still_open"], -r["score"], -r["pay_rank"],
                             -(r.get("salary_max") or 0),
                             r["days_live"] if r["days_live"] is not None else 999))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"updated": now.isoformat(timespec="minutes"), "count": len(rows), "jobs": rows}, f, indent=1)
    return rows
