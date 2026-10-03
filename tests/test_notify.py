"""The notifier is best-effort: it must never be able to fail a collection run."""
import pytest

from collector import notify


def job(**kw):
    base = {"title": "Data Engineer", "company": "Acme", "location": "Pune",
            "url": "https://x.test/1", "salary": ""}
    base.update(kw)
    return base


def res(score, **kw):
    out = {"score": score, "reason": "Close match.", "bullets": ["a", "b"]}
    out.update(kw)
    return out


class FakeResend:
    def __init__(self, status=200, boom=None):
        self.status, self.boom, self.calls = status, boom, []

    def post(self, url, **kw):
        self.calls.append(kw)
        if self.boom:
            raise self.boom
        return type("R", (), {"status_code": self.status, "text": "err"})()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_fake")
    monkeypatch.setenv("NOTIFY_EMAIL", "me@example.test")


def test_only_strong_scores_are_worth_an_email(monkeypatch):
    monkeypatch.setattr(notify.C, "NOTIFY_MIN_SCORE", 9)
    picked = notify.pick([(job(), res(7)), (job(), res(9)), (job(), res(10)), (job(), res(8))])
    assert [r["score"] for _, r in picked] == [10, 9], "strongest first, nothing below the bar"


def test_nothing_to_say_means_no_request(configured):
    s = FakeResend()
    assert notify.send([(job(), res(6))], s) == 0
    assert s.calls == []


def test_a_missing_key_is_not_an_error(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("NOTIFY_EMAIL", raising=False)
    s = FakeResend()
    assert notify.send([(job(), res(10))], s) == 0
    assert s.calls == [], "no key, no attempt, no crash"


def test_a_rejected_send_does_not_raise(configured):
    assert notify.send([(job(), res(10))], FakeResend(status=422)) == 0


def test_a_network_failure_does_not_raise(configured):
    assert notify.send([(job(), res(10))], FakeResend(boom=OSError("no route"))) == 0


def test_a_good_send_reports_how_many(configured, monkeypatch):
    monkeypatch.setattr(notify.C, "NOTIFY_MIN_SCORE", 9)
    s = FakeResend()
    assert notify.send([(job(), res(10)), (job(), res(9)), (job(), res(5))], s) == 2
    sent = s.calls[0]["json"]
    assert sent["to"] == ["me@example.test"]
    assert "10/10" in sent["html"] and "9/10" in sent["html"]
    assert "5/10" not in sent["html"]


def test_job_text_is_escaped_not_injected(configured):
    nasty = job(title="<script>alert(1)</script>", company="A & B")
    s = FakeResend()
    notify.send([(nasty, res(10))], s)
    body = s.calls[0]["json"]["html"]
    assert "<script>" not in body
    assert "&lt;script&gt;" in body and "A &amp; B" in body
