"""Deterministic filters. Cheap work goes in front of expensive work."""
from . import config as C


def keep(job, cfg=C):
    t = job["title"].lower()
    loc = job["location"].lower()
    if any(k in t for k in cfg.REJECT_TITLE):
        return False, "rejected title"
    if not any(k in t for k in cfg.MUST_MATCH_TITLE):
        return False, "not a data role"
    if job.get("days_live") is not None and job["days_live"] > cfg.MAX_AGE_DAYS:
        return False, "stale"
    if not any(k in loc for k in cfg.OK_LOCATION):
        return False, "location"
    return True, "ok"


def apply(jobs, cfg=C):
    kept, reasons = [], {}
    for j in jobs:
        ok, why = keep(j, cfg)
        if ok:
            kept.append(j)
        else:
            reasons[why] = reasons.get(why, 0) + 1
    return kept, reasons


def freshness(days):
    if days is None:
        return "unknown"
    if days <= 7:
        return "fresh"
    if days <= 21:
        return "recent"
    if days <= 45:
        return "ageing"
    return "stale"
