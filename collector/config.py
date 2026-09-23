"""Everything you'd want to tune lives here."""
import os

# ---- Watchlist ------------------------------------------------------------
# board = greenhouse | lever | ashby ; token = slug from the careers URL.
#   job-boards.greenhouse.io/SLUG   jobs.lever.co/SLUG   jobs.ashbyhq.com/SLUG
# A wrong slug is harmless: that company is skipped and the run continues.
COMPANIES = [
    {"board": "greenhouse", "token": "cloudflare"},
    {"board": "greenhouse", "token": "databricks"},
    {"board": "greenhouse", "token": "stripe"},
    {"board": "ashby", "token": "ramp"},
    {"board": "ashby", "token": "notion"},
    {"board": "lever", "token": "matchgroup"},
]

# ---- Cheap filters (run BEFORE any AI call) --------------------------------
ROLE_KEYWORDS = ["data analyst", "data engineer", "data scientist",
                 "analytics engineer", "business analyst",
                 "quantitative analyst", "software development engineer"]
LOCATIONS = ["India", "Bengaluru", "Hyderabad", "Pune", "Mumbai", "Gurugram"]
SALARY_TARGET = 1200000        # ranks jobs at/above this higher
HARD_SALARY_FLOOR = 0          # 0 = off
]
REJECT_TITLE = [
    "senior", "sr.", "staff", "principal", "director", "manager", "lead",
    "vp ", "head of", "sales", "account executive", "recruiter", "marketing",
    "software engineer", "distributed systems", "security",
]
OK_LOCATION = [
    "remote", "united states", "usa", "u.s.", "seattle", "san francisco",
    "new york", "austin", "boston", "chicago", "los angeles", "denver",
    ", wa", ", ca", ", ny", ", tx", ", ma", ", il", ", co",
]
MAX_AGE_DAYS = 30

# ---- Scoring --------------------------------------------------------------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
BATCH_SIZE = 8
MIN_SCORE = 7          # published to the site at or above this
DESCRIPTION_CHARS = 3000
SNIPPET_CHARS = 600    # kept in jobs.json so the site can rescore against a resume

# ---- Storage --------------------------------------------------------------
STORE_PATH = "data/scored.json"         # every job we've ever scored (private-ish)
PUBLISH_PATH = "public/data/jobs.json"  # what the website shows
PROFILE_PATH = "profile.md"
FORGET_AFTER_DAYS = 60
