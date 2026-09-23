import types

from collector import config as C, filters, normalize
from conftest import NOW, load

# A fixed config, so these tests describe the filtering RULES rather than
# whichever cities collector/config.py happens to target today.
CFG = types.SimpleNamespace(
    MUST_MATCH_TITLE=C.MUST_MATCH_TITLE,
    REJECT_TITLE=C.REJECT_TITLE,
    OK_LOCATION=["remote", "seattle", ", wa", ", ny", "new york"],
    MAX_AGE_DAYS=30,
)


def test_filters_drop_the_right_things():
    jobs = normalize.normalize("greenhouse", load("greenhouse.json"), now=NOW)
    kept, reasons = filters.apply(jobs, CFG)
    # "Software Engineer, Data Platform" now qualifies: SDE roles are in scope.
    assert [j["title"] for j in kept] == [
        "Data Engineer, People Analytics", "Software Engineer, Data Platform"]
    assert reasons == {"rejected title": 2, "stale": 1, "location": 1}


def test_freshness_buckets():
    assert filters.freshness(None) == "unknown"
    assert filters.freshness(3) == "fresh"
    assert filters.freshness(15) == "recent"
    assert filters.freshness(30) == "ageing"
    assert filters.freshness(200) == "stale"
