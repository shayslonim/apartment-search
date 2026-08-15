from apartment_search.analysis_worker import AnalysisWorker
from apartment_search.local_analyzer import (
    SEARCH_GUIDELINES,
    ApartmentAnalyzer,
    Place,
    WalkingRoute,
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
        return {
            "category": "recommended",
            "score": 87,
            "summary": "Strong Montefiore match with short verified walks.",
            "location_signal": "Montefiore",
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
    assert SEARCH_GUIDELINES in model.calls[1][0]
    assert '"minutes": 14' in model.calls[1][1]
    assert '"minutes": 11' in model.calls[1][1]


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
