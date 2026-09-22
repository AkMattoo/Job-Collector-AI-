"""End-to-end on fixtures: the at-least-once guarantee is the thing under test."""
import json

from collector import main
from conftest import NOW, FakeSession, gemini_reply

# after filters, survivors in order: Acme DE (gh), Ramp AE (ashby), Matchgroup Data Analyst (lever)
GOOD = gemini_reply([
    {"index": 0, "score": 9, "reason": "Direct match.", "bullets": ["a", "b", "c"], "salary": "$120,000–$150,000", "duration": "Full-time"},
    {"index": 1, "score": 8, "reason": "Close.", "bullets": ["a"], "salary": "", "duration": ""},
    {"index": 2, "score": 4, "reason": "Weak.", "bullets": [], "salary": "", "duration": ""},
])


def read(p):
    return json.loads(open(p).read())


def test_gemini_down_loses_nothing(workdir):
    s = FakeSession([("x", 503)] * 3)
    r = main.run("k", s, NOW)
    assert r["new"] == 3 and r["scored"] == 0
    assert read("data/scored.json") == {}           # nothing marked seen
    # next day Gemini is back: the same 3 jobs are still there to score
    r2 = main.run("k", FakeSession([GOOD]), NOW)
    assert r2["new"] == 3 and r2["scored"] == 3


def test_happy_path_publishes_only_good_scores(workdir):
    r = main.run("k", FakeSession([GOOD]), NOW)
    assert r == {"fetched": 9, "kept": 3, "new": 3, "scored": 3, "published": 2}
    pub = read("public/data/jobs.json")
    assert [j["company"] for j in pub["jobs"]] == ["Acme", "Ramp"]
    top = pub["jobs"][0]
    assert top["salary"] == "$120,000–$150,000" and top["freshness"] == "fresh" and top["still_open"]
    assert "description" not in top and len(top["snippet"]) <= 600


def test_second_run_does_not_rescore(workdir):
    main.run("k", FakeSession([GOOD]), NOW)
    s = FakeSession([])
    r = main.run("k", s, NOW)
    assert r["new"] == 0 and s.gemini_calls == 0
