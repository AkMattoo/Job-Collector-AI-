"""The new search sources: Adzuna and an Apify LinkedIn actor."""
from collector import filters, normalize, store
from conftest import NOW, load


def test_adzuna_pay_stated_vs_predicted():
    jobs = normalize.normalize("adzuna", load("adzuna.json")["results"], now=NOW)
    by_company = {j["company"]: j for j in jobs}
    stated = by_company["Acme"]
    assert stated["salary"] == "INR 1,200,000 - 1,800,000/yr"
    assert stated["salary_predicted"] is False
    assert stated["description"] == "SQL, Python & dashboards"
    assert stated["source"] == "adzuna"

    predicted = by_company["Beta"]
    assert "estimated, not stated" in predicted["salary"]
    assert predicted["salary_predicted"] is True

    assert by_company["Gamma"]["salary"] == ""   # no pay in the posting


def test_adzuna_open_roles_is_not_faked_for_a_search():
    # counting search hits would be meaningless, so it stays 0
    jobs = normalize.normalize("adzuna", load("adzuna.json")["results"], now=NOW)
    assert all(j["open_roles_at_company"] == 0 for j in jobs)


def test_apify_tolerates_different_field_names_and_junk():
    jobs = normalize.normalize("apify", load("apify.json"), now=NOW)
    assert [j["title"] for j in jobs] == ["Data Analyst", "Business Analyst"]
    assert jobs[0]["company"] == "Kappa" and jobs[0]["url"] == "https://li/1"
    assert jobs[1]["company"] == "Lambda" and jobs[1]["location"] == "Remote, India"
    assert all(j["source"] == "linkedin" for j in jobs)


def test_filters_drop_senior_overseas_and_too_experienced():
    jobs = normalize.normalize("adzuna", load("adzuna.json")["results"], now=NOW)
    kept, reasons = filters.apply(jobs)
    assert [j["company"] for j in kept] == ["Acme", "Beta", "Gamma"]
    assert reasons == {"rejected title": 1, "location": 1, "too senior": 1}


def test_unknown_pay_is_not_treated_as_low_pay():
    stated_high = {"salary_max": 2000000}
    stated_low = {"salary_max": 400000}
    unknown = {"salary_max": None, "salary_min": None}
    assert store._pay_rank(stated_high) == 2
    assert store._pay_rank(stated_low) == 1
    assert store._pay_rank(unknown) == 0


def test_ranking_puts_fit_first_then_pay(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    today = NOW.date().isoformat()
    base = dict(title="t", company="c", location="l", duration="", posted="",
                open_roles_at_company=0, why_it_fits="", tailored_bullets=[],
                snippet="", found_on=today, last_seen_open=today)
    db = {
        "u1": {**base, "score": 8, "salary_max": None, "url": "u1"},
        "u2": {**base, "score": 8, "salary_max": 2000000, "url": "u2"},
        "u3": {**base, "score": 9, "salary_max": None, "url": "u3"},
        "u4": {**base, "score": 8, "salary_max": 500000, "url": "u4"},
    }
    rows = store.publish(db, NOW, path=str(tmp_path / "out.json"))
    # 9 first; then among the 8s: above-target pay, below-target pay, unknown
    assert [r["url"] for r in rows] == ["u3", "u2", "u4", "u1"]
