"""The scored-jobs store. A job counts as 'seen' only once it has a score.
Recording happens after scoring succeeds, never before, so failures are retried."""
import json
import os
from datetime import datetime, timedelta, timezone

from . import config as C
from .filters import freshness


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


def publish(store, now, path=C.PUBLISH_PATH):
    today = now.date().isoformat()
    rows = []
    for v in store.values():
        if v["score"] < C.MIN_SCORE:
            continue
        days = None
        if v.get("posted"):
            try:
                dt = datetime.fromisoformat(v["posted"].replace("Z", "+00:00"))
                days = (now - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).days
            except ValueError:
                pass
        rows.append({**v, "days_live": days, "freshness": freshness(days),
                     "still_open": v.get("last_seen_open") == today})
    rows.sort(key=lambda r: (not r["still_open"], -r["score"], r["days_live"] if r["days_live"] is not None else 999))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"updated": now.isoformat(timespec="minutes"), "count": len(rows), "jobs": rows}, f, indent=1)
    return rows
