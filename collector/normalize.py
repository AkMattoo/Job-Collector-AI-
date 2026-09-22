"""Three API shapes in, one shape out. Nothing downstream knows which board a job came from."""
import html
import re
from datetime import datetime, timezone

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(text):
    # Greenhouse double-encodes: the HTML itself is escaped, and entities inside
    # it are escaped again. Unescape, strip tags, unescape what's left.
    once = html.unescape(text or "")
    return _WS.sub(" ", html.unescape(_TAGS.sub(" ", once))).strip()


def _pretty(slug):
    return (slug or "").replace("-", " ").replace("_", " ").title()


def _iso(ms_or_str):
    if ms_or_str in (None, ""):
        return ""
    if isinstance(ms_or_str, (int, float)):
        return datetime.fromtimestamp(ms_or_str / 1000, tz=timezone.utc).isoformat()
    return str(ms_or_str)


def greenhouse(payload):
    for j in payload.get("jobs", []):
        yield {
            "company": j.get("company_name", ""),
            "title": (j.get("title") or "").strip(),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "posted": j.get("first_published") or j.get("updated_at") or "",
            "duration": "",
            "salary": "",
            "description": _clean(j.get("content")),
        }


def ashby(payload):
    for j in payload.get("jobs", []):
        if j.get("isListed") is False:
            continue
        url = j.get("jobUrl", "")
        yield {
            "company": _pretty(url.split("/")[3] if url.count("/") >= 3 else ""),
            "title": (j.get("title") or "").strip(),
            "location": j.get("location", ""),
            "url": url,
            "posted": j.get("publishedAt", ""),
            "duration": j.get("employmentType", ""),
            "salary": (j.get("compensation") or {}).get("compensationTierSummary", ""),
            "description": _clean(j.get("descriptionPlain")),
        }


def lever(payload):
    for j in payload if isinstance(payload, list) else []:
        url = j.get("hostedUrl", "")
        sr = j.get("salaryRange") or {}
        salary = ""
        if sr:
            salary = f"{sr.get('currency', '')} {sr.get('min', '')}-{sr.get('max', '')} / {sr.get('interval', '')}".strip()
        cats = j.get("categories") or {}
        yield {
            "company": _pretty(url.split("/")[3] if url.count("/") >= 3 else ""),
            "title": (j.get("text") or "").strip(),
            "location": cats.get("location", ""),
            "url": url,
            "posted": _iso(j.get("createdAt")),
            "duration": cats.get("commitment", ""),
            "salary": salary,
            "description": _clean(j.get("descriptionPlain")),
        }


PARSERS = {"greenhouse": greenhouse, "ashby": ashby, "lever": lever}


def normalize(board, payload, now=None):
    """Normalize one board payload and attach computed signals."""
    now = now or datetime.now(timezone.utc)
    jobs = [j for j in PARSERS[board](payload) if j["url"] and j["title"]]
    open_roles = len(jobs)  # roles this company has open right now - a real signal
    for j in jobs:
        j["days_live"] = _days_since(j["posted"], now)
        j["open_roles_at_company"] = open_roles
    return jobs


def _days_since(posted, now):
    if not posted:
        return None
    try:
        dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)
    except ValueError:
        return None
