import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)
FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


class Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Serves fixture payloads for board URLs and scripted replies for Gemini."""

    def __init__(self, gemini_replies=None):
        self.gemini_replies = list(gemini_replies or [])
        self.gemini_calls = 0

    def get(self, url, timeout=None):
        if "does-not-exist" in url:
            return Resp({}, 404)
        if "greenhouse" in url:
            return Resp(load("greenhouse.json"))
        if "lever" in url:
            return Resp(load("lever.json"))
        if "ashby" in url:
            return Resp(load("ashby.json"))
        return Resp({}, 404)

    def post(self, url, headers=None, json=None, timeout=None):
        self.gemini_calls += 1
        reply = self.gemini_replies.pop(0) if self.gemini_replies else ("fail", 503)
        if isinstance(reply, tuple):
            return Resp({}, reply[1])
        return Resp(reply)


def gemini_reply(items):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(items)}]}}]}


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    from collector import config as C
    monkeypatch.chdir(tmp_path)
    (tmp_path / "profile.md").write_text("Test profile")
    monkeypatch.setattr(C, "COMPANIES", [
        {"board": "greenhouse", "token": "acme"},
        {"board": "ashby", "token": "ramp"},
        {"board": "lever", "token": "matchgroup"},
        {"board": "greenhouse", "token": "does-not-exist"},
    ])
    monkeypatch.setattr(C, "USE_BOARDS", True)
    monkeypatch.setattr(C, "USE_ADZUNA", False)
    monkeypatch.setattr(C, "USE_LINKEDIN", False)
    monkeypatch.setattr(C, "OK_LOCATION", ["remote", "seattle", ", wa", ", ny", "new york"])
    monkeypatch.setattr(C, "MAX_AGE_DAYS", 30)
    import collector.scorer as S
    monkeypatch.setattr(S.time, "sleep", lambda *_: None)
    return tmp_path
