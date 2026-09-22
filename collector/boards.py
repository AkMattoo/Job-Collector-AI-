"""Fetch raw postings from each board's public JSON API."""
import logging
import requests

log = logging.getLogger(__name__)

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{t}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true",
}


def fetch(company: dict, session=None, timeout=20):
    """Return (board, payload) or None. One bad company never kills the run."""
    s = session or requests
    url = URLS[company["board"]].format(t=company["token"])
    try:
        r = s.get(url, timeout=timeout)
        r.raise_for_status()
        return company["board"], r.json()
    except Exception as e:  # noqa: BLE001 - deliberately broad, we log and move on
        log.warning("skip %s/%s: %s", company["board"], company["token"], e)
        return None
