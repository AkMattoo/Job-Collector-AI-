from collector import normalize
from conftest import NOW, load


def test_greenhouse_decodes_and_strips_html():
    jobs = normalize.normalize("greenhouse", load("greenhouse.json"), now=NOW)
    j = jobs[0]
    assert j["description"] == "Build ETL in BigQuery. Pay: $120,000–$150,000"
    assert j["location"] == "Seattle, WA"
    assert j["days_live"] == 2
    assert j["open_roles_at_company"] == 6


def test_ashby_skips_unlisted_and_reads_comp():
    jobs = normalize.normalize("ashby", load("ashby.json"), now=NOW)
    assert [j["title"] for j in jobs] == ["Analytics Engineer"]
    assert jobs[0]["company"] == "Ramp"
    assert jobs[0]["salary"] == "$137K – $180K"
    assert jobs[0]["description"] == "dbt and SQL"


def test_lever_salary_and_timestamp():
    jobs = normalize.normalize("lever", load("lever.json"), now=NOW)
    assert jobs[1]["salary"] == "USD 40-55 / per-hour-wage"
    assert jobs[1]["duration"] == "Internship"
    assert jobs[1]["posted"].startswith("2026-09-19")
    assert jobs[1]["days_live"] == 3


def test_all_boards_share_one_shape():
    keys = None
    for board, fx in [("greenhouse", "greenhouse.json"), ("ashby", "ashby.json"), ("lever", "lever.json")]:
        for j in normalize.normalize(board, load(fx), now=NOW):
            keys = keys or set(j)
            assert set(j) == keys
