"""Entry point: python -m collector.main"""
import logging
import os
import sys
from datetime import datetime, timezone

import requests

from . import boards, config as C, filters, normalize, scorer, store

log = logging.getLogger("collector")


def run(api_key, session=None, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    session = session or requests.Session()
    profile = open(C.PROFILE_PATH, encoding="utf-8").read().strip()
    db = store.load()

    # 1. fetch + normalize
    jobs = []
    for company in C.COMPANIES:
        got = boards.fetch(company, session)
        if got:
            jobs.extend(normalize.normalize(*got, now=now))
    log.info("fetched %d postings from %d companies", len(jobs), len(C.COMPANIES))

    # 2. note which stored jobs are still live, forget old ones
    store.mark_open(db, {j["url"] for j in jobs}, today)
    store.prune(db, now)

    # 3. cheap filters, then drop anything already scored
    kept, reasons = filters.apply(jobs)
    new = [j for j in kept if j["url"] not in db]
    log.info("filtered to %d (dropped: %s); %d not yet scored", len(kept), reasons, len(new))

    # 4. score, recording each job only once it has a score
    scored = 0
    for job, result in scorer.score(new, profile, api_key, session):
        store.record(db, job, result, today)
        scored += 1
    log.info("scored %d of %d new jobs", scored, len(new))

    store.save(db)
    rows = store.publish(db, now)
    log.info("published %d matches (score >= %d)", len(rows), C.MIN_SCORE)
    return {"fetched": len(jobs), "kept": len(kept), "new": len(new), "scored": scored, "published": len(rows)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set")
    print(run(key))
