"""Batch-score jobs against a profile with Gemini. Structured output, never trusted blindly."""
import json
import logging
import time

import requests

from . import config as C

log = logging.getLogger(__name__)
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"

PROMPT = """You are screening job postings for one specific candidate.

CANDIDATE PROFILE:
{profile}

For each job, return an object with:
- index: the JOB number
- score: integer 0-10 for fit. Be strict. 10 = apply today; below 6 = do not bother.
  Penalise heavily if it needs years of experience the candidate lacks, or is not a data role.
- reason: one sentence, max 15 words, plain language.
- bullets: 3 resume bullets tailored to THIS job, using only the candidate's real experience. Each under 20 words.
- salary: pay EXACTLY as stated in the posting, else "". Never estimate.
- duration: employment type or length EXACTLY as stated, else "".

{jobs}"""

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "index": {"type": "INTEGER"},
            "score": {"type": "INTEGER"},
            "reason": {"type": "STRING"},
            "bullets": {"type": "ARRAY", "items": {"type": "STRING"}},
            "salary": {"type": "STRING"},
            "duration": {"type": "STRING"},
        },
        "required": ["index", "score", "reason"],
    },
}


def build_prompt(profile, batch):
    listing = "\n\n".join(
        f"### JOB {i}\nTitle: {j['title']}\nCompany: {j['company']}\nLocation: {j['location']}\n"
        f"Known pay: {j['salary'] or 'not given'}\nKnown type: {j['duration'] or 'not given'}\n"
        f"Description: {j['description'][:C.DESCRIPTION_CHARS]}"
        for i, j in enumerate(batch)
    )
    return PROMPT.format(profile=profile, jobs=listing)


def parse(response_json, batch):
    """Map Gemini's reply back onto the batch. Returns {index: result}; {} on any garbage."""
    try:
        text = response_json["candidates"][0]["content"]["parts"][0]["text"]
        items = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return {}
    out = {}
    for it in items if isinstance(items, list) else []:
        idx = it.get("index")
        if isinstance(idx, int) and 0 <= idx < len(batch) and isinstance(it.get("score"), int):
            out[idx] = it
    return out


class QuotaExhausted(Exception):
    """The daily free-tier budget is gone. Retrying cannot help: it resets on a
    clock, not on a timer. Raised so the run stops instead of burning requests."""

def auth_headers(api_key):
    """x-goog-api-key works for both old AIza keys and the new AQ. auth keys -
    confirmed against the live API, where an AQ. key on a bearer header returns
    401. Bearer is kept only as a fallback in case that ever changes."""
    key = api_key.strip()
    return [{"x-goog-api-key": key}, {"Authorization": f"Bearer {key}"}]


def call(prompt, api_key, session=None, retries=3):
    s = session or requests
    header_choices = auth_headers(api_key)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    for attempt in range(retries):
        try:
            r = None
            for i, headers in enumerate(header_choices):
                r = s.post(
                    ENDPOINT.format(m=C.GEMINI_MODEL),
                    headers=headers,
                    json=body,
                    timeout=120,
                )
                text = getattr(r, "text", "") or ""
                auth_problem = r.status_code in (401, 403) or (
                    r.status_code == 400 and "API_KEY_INVALID" in text
                )
                if not auth_problem:
                    break
                log.warning("gemini auth attempt %d rejected (HTTP %s)", i + 1, r.status_code)
                        if r.status_code == 429:
                raise QuotaExhausted(getattr(r, "text", "")[:200])
            if r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}: {getattr(r, 'text', '')[:300]}")
            if r.status_code >= 400:
                log.error("gemini rejected the request (HTTP %s): %s", r.status_code, getattr(r, "text", "")[:300])
                return None
            r.raise_for_status()
            return r.json()
                except QuotaExhausted:
            raise                       # never retried - see the class docstring
        except Exception as e:  # noqa: BLE001
            wait = 10 * (attempt + 1)   # 503 'high demand' needs real backoff
            log.warning("gemini attempt %d failed (%s), waiting %ds", attempt + 1, e, wait)
            time.sleep(wait)
    return None


def score(jobs, profile, api_key, session=None, pause=4):
    """Yield (job, result) only for jobs that were actually scored.
    Jobs in a failed batch are simply not yielded - so they are NOT recorded
    and get retried next run (at-least-once)."""
        budget = C.MAX_GEMINI_CALLS_PER_RUN
    for start in range(0, len(jobs), C.BATCH_SIZE):
        if budget <= 0:
            log.warning("hit the %d-call budget for this run; %d jobs deferred",
                        C.MAX_GEMINI_CALLS_PER_RUN, len(jobs) - start)
            return
        batch = jobs[start:start + C.BATCH_SIZE]
        try:
            resp = call(build_prompt(profile, batch), api_key, session)
        except QuotaExhausted:
            log.warning("daily Gemini quota is gone; stopping with %d jobs unscored "
                        "(they are not recorded, so the next run picks them up)",
                        len(jobs) - start)
            return
        budget -= 1
        results = parse(resp, batch) if resp else {}
        if not results:
            log.warning("batch at %d produced no scores; will retry next run", start)
        for idx, res in results.items():
            yield batch[idx], res
        if pause:
            time.sleep(pause)
