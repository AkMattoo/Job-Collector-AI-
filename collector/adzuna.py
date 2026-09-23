"""Adzuna job search. One request per role keyword per location.

Docs: https://developer.adzuna.com/  — free developer key, no card.
Set ADZUNA_APP_ID and ADZUNA_APP_KEY as secrets.
"""
import logging
import os

import requests

from . import config as C

log = logging.getLogger(__name__)
URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


def available():
    return bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY"))


def search(keyword, where, session=None, timeout=25):
    """Return the raw results list for one keyword+location, or [] on failure."""
    s = session or requests
    params = {
        "app_id": os.environ.get("ADZUNA_APP_ID", ""),
        "app_key": os.environ.get("ADZUNA_APP_KEY", ""),
        "what": keyword,
        "where": where,
        "results_per_page": C.ADZUNA_PER_SEARCH,
        "max_days_old": C.MAX_AGE_DAYS,
        "sort_by": "date",
        "content-type": "application/json",
    }
    try:
        r = s.get(URL.format(country=C.ADZUNA_COUNTRY), params=params, timeout=timeout)
        if r.status_code == 401:
            log.error("Adzuna rejected the credentials. Check ADZUNA_APP_ID / ADZUNA_APP_KEY.")
            return []
        if not getattr(r, "ok", r.status_code < 400):
            log.warning("Adzuna %s for %r in %r: %s", r.status_code, keyword, where,
                        getattr(r, "text", "")[:200])
            return []
        return r.json().get("results", [])
    except Exception as e:  # noqa: BLE001 - one failed search never kills the run
        log.warning("Adzuna search failed for %r in %r: %s", keyword, where, e)
        return []


def fetch_all(session=None):
    out = []
    for keyword in C.ROLE_KEYWORDS:
        for where in C.LOCATIONS:
            found = search(keyword, where, session)
            log.info("adzuna: %-28s %-12s -> %d", keyword, where, len(found))
            out.extend(found)
    return out
