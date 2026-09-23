"""LinkedIn jobs via an Apify actor.

Apify runs someone else's scraper for you and hands back the rows. You pick the
actor in the Apify console, then set:
    APIFY_TOKEN  - your Apify API token
    APIFY_ACTOR  - the actor id, e.g. "bebity~linkedin-jobs-scraper"

Actors differ in the field names they return, so the parser in normalize.py is
deliberately forgiving about where the title / company / url live.
"""
import logging
import os

import requests

from . import config as C

log = logging.getLogger(__name__)
RUN_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def available():
    return bool(os.environ.get("APIFY_TOKEN") and C.APIFY_ACTOR)


def fetch_all(session=None, timeout=240):
    if not available():
        log.info("linkedin: skipped (APIFY_TOKEN or APIFY_ACTOR not set)")
        return []
    s = session or requests
    out = []
    for keyword in C.ROLE_KEYWORDS:
        payload = {
            "title": keyword,
            "keyword": keyword,          # actors disagree on the key name;
            "searchQuery": keyword,      # harmless extras are ignored
            "location": C.LOCATIONS[0],
            "rows": C.APIFY_PER_SEARCH,
            "maxItems": C.APIFY_PER_SEARCH,
            "publishedAt": "r2592000",   # last 30 days, where supported
        }
        try:
            r = s.post(
                RUN_URL.format(actor=C.APIFY_ACTOR),
                params={"token": os.environ.get("APIFY_TOKEN", "")},
                json=payload,
                timeout=timeout,
            )
            if not getattr(r, "ok", r.status_code < 400):
                log.warning("apify %s for %r: %s", r.status_code, keyword,
                            getattr(r, "text", "")[:200])
                continue
            rows = r.json()
            log.info("linkedin: %-28s -> %d", keyword, len(rows) if isinstance(rows, list) else 0)
            if isinstance(rows, list):
                out.extend(rows)
        except Exception as e:  # noqa: BLE001
            log.warning("apify run failed for %r: %s", keyword, e)
    return out
