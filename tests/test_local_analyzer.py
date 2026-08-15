from apartment_search.analysis_worker import AnalysisWorker
from apartment_search.local_analyzer import (
    SEARCH_GUIDELINES,
    ApartmentAnalyzer,
    JsonCache,
    NominatimGeocoder,
    Place,
    WalkingRoute,
    canonicalize_location_query,
    is_tel_aviv_candidate,
    normalize_listing_text,
)


class FakeModel:
    model = "qwen3:8b"

    def __init__(self):
        self.calls = []

    def generate(self, system, user, schema):
        self.calls.append((system, user, schema))
        if len(self.calls) == 1:
            return {
                "location_query": "Montefiore, Tel Aviv",
                "location_text": "Montefiore",
                "location_confidence": "medium",
                "listing_type": "shared",
                "price_ils": 3900,
                "move_in_signal": "match",
                "condition_signal": "good",
                "shelter_signal": "unknown",
                "facts": ["Bright shared apartment"],
                "concerns": [],
                "unknowns": ["Protection details are missing"],
            }
        if len(self.calls) == 2:
            return {"shelter_signal": "unknown"}
        return {
            "category": "recommended",
            "score": 87,
            "summary": "Strong Montefiore match with short verified walks.",
            "location_signal": "Montefiore",
            "shelter_signal": "unknown",
            "positives": ["Short walk to work", "Within budget"],
            "concerns": [],
            "unknowns": ["Protection details are missing"],
        }


class FakeGeocoder:
    def geocode(self, query):
        if "Montefiore" in query:
            return Place("Montefiore, Tel Aviv", 32.063, 34.779)
        if "HaHaskala" in query:
            return Place("HaHaskala 3", 32.070, 34.793)
        if "Sarona" in query:
            return Place("Sarona Market", 32.071, 34.787)
        return None


class FakeRouter:
    def route(self, origin, destination):
        if destination.label == "HaHaskala 3":
            return WalkingRoute(minutes=14, meters=1050)
        return WalkingRoute(minutes=11, meters=820)


def test_analyzer_grounds_final_verdict_with_routes_and_guidelines():
    model = FakeModel()
    analyzer = ApartmentAnalyzer(model, FakeGeocoder(), FakeRouter())

    result = analyzer.analyze(
        {
            "body": (
                "Room in a bright Montefiore apartment, 3900 ILS, available "
                "September 2026."
            )
        }
    )

    assert result["category"] == "recommended"
    assert result["walk_to_work_minutes"] == 14
    assert result["walk_to_sarona_minutes"] == 11
    assert result["model"] == "qwen3:8b"
    assert SEARCH_GUIDELINES in model.calls[2][0]
    assert "\u05de\u05de\u05d3" in model.calls[0][0]
    assert "\u05de\u05e7\u05dc\u05d8" in model.calls[0][0]
    assert "Classify only" in model.calls[1][0]
    assert '"minutes": 14' in model.calls[2][1]
    assert '"minutes": 11' in model.calls[2][1]


class FakeQueue:
    def __init__(self):
        self.job = {"id": "post-1", "claim_id": "claim-1", "body": "Listing"}
        self.completed = None
        self.failed = None

    def claim(self):
        job, self.job = self.job, None
        return job

    def complete(self, job, result):
        self.completed = (job, result)

    def fail(self, job, error):
        self.failed = (job, error)


class FakeAnalyzer:
    def analyze(self, job):
        return {"category": "just_okay", "score": 63}


def test_worker_returns_completed_result_to_hosted_queue():
    queue = FakeQueue()
    worker = AnalysisWorker(queue, FakeAnalyzer())

    assert worker.run_once() is True
    assert queue.completed[1] == {"category": "just_okay", "score": 63}
    assert queue.failed is None
    assert worker.run_once() is False


def test_canonicalizes_misspelled_montefiore_and_sarona_queries():
    assert canonicalize_location_query("MONTIFIORI, Tel Aviv") == (
        "Montefiore, Tel Aviv-Yafo, Israel"
    )
    assert canonicalize_location_query("\u05de\u05d5\u05e0\u05d8\u05d9\u05e4\u05d9\u05d5\u05e8\u05d9") == (
        "Montefiore, Tel Aviv-Yafo, Israel"
    )
    assert canonicalize_location_query("near Sarona") == (
        "Sarona Market, Tel Aviv-Yafo, Israel"
    )


def test_tel_aviv_candidate_uses_municipality_not_district_label():
    assert is_tel_aviv_candidate(
        {
            "display_name": "Montefiore, Tel Aviv district, Israel",
            "address": {"town": "Or Yehuda", "state_district": "Tel Aviv"},
        }
    ) is False
    assert is_tel_aviv_candidate(
        {
            "display_name": "Montefiore, Tel Aviv-Yafo, Israel",
            "address": {"city": "\u05ea\u05dc\u05be\u05d0\u05d1\u05d9\u05d1\u2013\u05d9\u05e4\u05d5"},
        }
    ) is True


def test_geocoder_does_not_fall_back_to_another_city(tmp_path):
    cache = JsonCache(tmp_path / "map.sqlite3")
    cache.put(
        "geocode:somewhere, tel aviv",
        [
            {
                "display_name": "Somewhere, Or Yehuda, Tel Aviv district, Israel",
                "lat": "32.03",
                "lon": "34.84",
                "address": {"town": "Or Yehuda"},
            }
        ],
    )
    try:
        assert NominatimGeocoder(cache).geocode("Somewhere, Tel Aviv") is None
    finally:
        cache.close()


def test_normalizes_hebrew_quote_marks_for_mamad_extraction():
    assert normalize_listing_text("\u05d9\u05e9 \u05de\u05de\u05f4\u05d3 \u05d5\u05de\u05e7\u05dc\u05d8") == '\u05d9\u05e9 \u05de\u05de"\u05d3 \u05d5\u05de\u05e7\u05dc\u05d8'
