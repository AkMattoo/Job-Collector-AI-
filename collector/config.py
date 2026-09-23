"""Everything you'd want to tune lives here."""
import os

# ---- What to search for ---------------------------------------------------
# Each entry becomes one search against each enabled source.
ROLE_KEYWORDS = [
    "data analyst",
    "data engineer",
    "data scientist",
    "analytics engineer",
    "business analyst",
    "quantitative analyst",
    "software development engineer",
]

# Where. Adzuna matches these loosely; LinkedIn wants them as written.
LOCATIONS = ["India", "Bengaluru", "Hyderabad", "Pune", "Mumbai", "Gurugram"]

# ---- Sources --------------------------------------------------------------
# Turn a source off here and the run skips it entirely.
USE_ADZUNA = True
USE_LINKEDIN = bool(os.environ.get("APIFY_TOKEN"))   # only if the token exists
USE_BOARDS = False                                   # the old per-company watchlist

ADZUNA_COUNTRY = "in"          # "in" = India. "us", "gb" etc. also exist.
ADZUNA_PER_SEARCH = 50         # results per keyword, max 50
APIFY_ACTOR = os.environ.get("APIFY_ACTOR", "")      # e.g. "bebity~linkedin-jobs-scraper"
APIFY_PER_SEARCH = 40

# Kept for the old board-based mode (USE_BOARDS = True)
COMPANIES = [
    {"board": "greenhouse", "token": "razorpaysoftwareprivatelimited"},
    {"board": "lever", "token": "meesho"},
    {"board": "lever", "token": "zeta"},
    {"board": "ashby", "token": "atlan"},
]

# ---- Cheap filters (run BEFORE any AI call) --------------------------------
MUST_MATCH_TITLE = [
    "data analyst", "data engineer", "data scientist", "analytics",
    "machine learning", "ml engineer", "business intelligence",
    "quantitative", "quant ", "business analyst",
    "software engineer", "software development engineer", "sde",
]
# Seniority and function filters. These keep senior roles away from the AI.
REJECT_TITLE = [
    "senior", "sr.", "sr ", "staff", "principal", "director", "head of",
    "manager", "lead ", "vp ", "vice president", "architect",
    "sales", "account executive", "recruiter", "marketing", "counsel",
    "legal", "teacher", "nurse",
]
# Phrases in the description that mean "too senior", checked after normalisation.
REJECT_DESCRIPTION = [
    "5+ years", "6+ years", "7+ years", "8+ years", "10+ years",
    "minimum of 5 years", "at least 5 years",
]
OK_LOCATION = [
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai",
    "mumbai", "delhi", "gurgaon", "gurugram", "noida", "kolkata",
    "ahmedabad", "jaipur", "coimbatore", "vellore", "trivandrum",
    "remote",
]
MAX_AGE_DAYS = 30

# ---- Pay ------------------------------------------------------------------
# Pay is a RANKING signal, not a cutoff: most Indian postings don't state it,
# so filtering on it would throw away good jobs whose pay is simply unknown.
SALARY_TARGET = 1200000        # annual, in the source's currency (INR for "in")
SALARY_CURRENCY = "INR"
HARD_SALARY_FLOOR = 0          # set above 0 to actually drop jobs below it

# ---- Scoring --------------------------------------------------------------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
BATCH_SIZE = 8
MIN_SCORE = 7
DESCRIPTION_CHARS = 3000
SNIPPET_CHARS = 600

# ---- Storage --------------------------------------------------------------
STORE_PATH = "data/scored.json"
PUBLISH_PATH = "public/data/jobs.json"
PROFILE_PATH = "profile.md"
FORGET_AFTER_DAYS = 60
