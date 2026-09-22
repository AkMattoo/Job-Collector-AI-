from collector import filters, normalize
from conftest import NOW, load


def test_filters_drop_the_right_things():
    jobs = normalize.normalize("greenhouse", load("greenhouse.json"), now=NOW)
    kept, reasons = filters.apply(jobs)
    assert [j["title"] for j in kept] == ["Data Engineer, People Analytics"]
    assert reasons == {"rejected title": 3, "stale": 1, "location": 1}


def test_freshness_buckets():
    assert filters.freshness(None) == "unknown"
    assert filters.freshness(3) == "fresh"
    assert filters.freshness(15) == "recent"
    assert filters.freshness(30) == "ageing"
    assert filters.freshness(200) == "stale"
