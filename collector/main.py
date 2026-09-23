"""Entry point: python -m collector.main"""
import logging
import os
import sys
from datetime import datetime, timezone

import requests

from . import adzuna, boards, config as C, filters, linkedin, normalize, scorer, store

log = logging.getLogger("collector")


def run(api_key, session=None, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    session = session or requests.Session()
    profile = open(C.PROFILE_PATH, encoding="utf-8").read().strip()
    db = store.load()

    # 1. fetch from every enabled source, then flatten into one shape
    jobs = []

    if C.USE_ADZUNA:
        if adzuna.available():
            jobs += normalize.normalize("adzuna", adzuna.fetch_all(session), now=now)
        else:
            log.warning("Adzuna is on but ADZUNA_APP_ID / ADZUNA_APP_KEY are not set; skipping")

    if C.USE_LINKEDIN:
        jobs += normalize.normalize("apify", linkedin.fetch_all(session), now=now)

    if C.USE_BOARDS:
        for company in C.COMPANIES:
            got = boards.fetch(company, session)
            if got:
                jobs.extend(normalize.normalize(*got, now=now))

    # the same job can come back from more than one source
    seen_urls, deduped = set(), []
    for j in jobs:
        if j["url"] in seen_urls:
            continue
        seen_urls.add(j["url"])
        deduped.append(j)
    if len(deduped) != len(jobs):
        log.info("dropped %d duplicate postings across sources", len(jobs) - len(deduped))
    jobs = deduped
    log.info("fetched %d postings", len(jobs))

    # 2. note which stored jobs are still live, forget old ones
    store.mark_open(db, {j["url"] for j in jobs}, today)
    store.prune(db, now)

    # 3. cheap filters, then drop anything already scored
    kept, reasons = filters.apply(jobs)
    new = [j for j in kept if j["url"] not in db]
    log.info("filtered to %d (dropped: %s); %d not yet scored", len(kept), reasons, len(new))
    
    # Over the cap, score the freshest first; the rest are left unscored and,
    # because only scored jobs get recorded, come back on the next run.
    if len(new) > C.MAX_TO_SCORE:
        log.info("capping at %d this run; %d deferred to the next run",
                 C.MAX_TO_SCORE, len(new) - C.MAX_TO_SCORE)
        new = sorted(new, key=lambda j: j.get("days_live", 999))[:C.MAX_TO_SCORE]

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
