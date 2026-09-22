import json

from collector import scorer
from conftest import FakeSession, gemini_reply

BATCH = [{"title": "a"}, {"title": "b"}]


def test_parse_valid():
    out = scorer.parse(gemini_reply([{"index": 0, "score": 9, "reason": "x"}, {"index": 1, "score": 3, "reason": "y"}]), BATCH)
    assert out[0]["score"] == 9 and out[1]["score"] == 3


def test_parse_rejects_garbage_and_bad_indexes():
    assert scorer.parse({"candidates": [{"content": {"parts": [{"text": "sorry"}]}}]}, BATCH) == {}
    assert scorer.parse({"error": {"code": 429}}, BATCH) == {}
    out = scorer.parse(gemini_reply([{"index": 7, "score": 9, "reason": "x"}, {"index": 0, "score": "9"}]), BATCH)
    assert out == {}


def test_failed_batch_yields_nothing(monkeypatch):
    monkeypatch.setattr(scorer.time, "sleep", lambda *_: None)
    s = FakeSession([("x", 503), ("x", 503), ("x", 503)])
    assert list(scorer.score([{"title": "a", "company": "", "location": "", "salary": "",
                               "duration": "", "description": ""}], "p", "k", s)) == []
    assert s.gemini_calls == 3  # retried
