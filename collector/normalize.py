"""Three API shapes in, one shape out. Nothing downstream knows which board a job came from."""
import html
import re
from datetime import datetime, timezone

from . import config as C

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


def adzuna(payload):
    """Adzuna search results. Pay is often present but may be PREDICTED, not stated."""
    for j in payload if isinstance(payload, list) else []:
        lo, hi = j.get("salary_min"), j.get("salary_max")
        predicted = str(j.get("salary_is_predicted", "0")) in ("1", "true", "True")
        yield {
            "company": ((j.get("company") or {}).get("display_name") or "").strip(),
            "title": (j.get("title") or "").strip(),
            "location": ((j.get("location") or {}).get("display_name") or "").strip(),
            "url": j.get("redirect_url", ""),
            "posted": j.get("created", ""),
            "duration": j.get("contract_time", "") or j.get("contract_type", "") or "",
            "salary": _pay(lo, hi, predicted),
            "salary_min": lo, "salary_max": hi, "salary_predicted": predicted,
            "description": _clean(j.get("description")),
            "source": "adzuna",
        }


# Apify actors disagree on field names, so try several for each field.
def _first(d, *keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (str, int, float)) and str(v).strip():
            return str(v).strip()
        if isinstance(v, dict):
            for inner in ("name", "displayName", "title", "text"):
                if v.get(inner):
                    return str(v[inner]).strip()
    return ""


def apify(payload):
    """Rows from a LinkedIn jobs actor on Apify."""
    for j in payload if isinstance(payload, list) else []:
        if not isinstance(j, dict):
            continue
        yield {
            "company": _first(j, "companyName", "company", "companyTitle", "organization"),
            "title": _first(j, "title", "jobTitle", "position", "name"),
            "location": _first(j, "location", "jobLocation", "place", "formattedLocation"),
            "url": _first(j, "url", "link", "jobUrl", "applyUrl", "jobPostingUrl"),
            "posted": _first(j, "postedAt", "publishedAt", "postedDate", "listedAt", "date"),
            "duration": _first(j, "employmentType", "contractType", "jobType"),
            "salary": _first(j, "salary", "salaryInfo", "compensation"),
            "salary_min": None, "salary_max": None, "salary_predicted": False,
            "description": _clean(_first(j, "descriptionText", "description", "jobDescription", "snippet")),
            "source": "linkedin",
        }


def _pay(lo, hi, predicted):
    if not lo and not hi:
        return ""
    def fmt(v):
        return f"{int(v):,}" if isinstance(v, (int, float)) else ""
    span = f"{fmt(lo)} - {fmt(hi)}".strip(" -")
    tag = " (estimated, not stated in the posting)" if predicted else ""
    return f"{C.SALARY_CURRENCY} {span}/yr{tag}"


PARSERS = {"greenhouse": greenhouse, "ashby": ashby, "lever": lever,
           "adzuna": adzuna, "apify": apify}


DEFAULTS = {"salary_min": None, "salary_max": None, "salary_predicted": False,
            "source": "board"}


def normalize(board, payload, now=None):
    """Normalize one source's payload and attach computed signals."""
    now = now or datetime.now(timezone.utc)
    jobs = []
    for j in PARSERS[board](payload):
        if not (j.get("url") and j.get("title")):
            continue
        for k, v in DEFAULTS.items():
            j.setdefault(k, v)
        jobs.append(j)

    # For a company board, every job came from the same company, so the count
    # is a real "how much is this company hiring" signal. For a search source
    # it would just count search hits, so leave it at 0.
    per_company = len(jobs) if board in ("greenhouse", "ashby", "lever") else 0
    for j in jobs:
        j["days_live"] = _days_since(j["posted"], now)
        j["open_roles_at_company"] = per_company
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
