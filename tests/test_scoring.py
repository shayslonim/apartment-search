from apartment_search.models import ApartmentPost, Criteria, Decision
from apartment_search.scoring import parse_price_ils, score_post


def test_parse_price_ignores_move_in_year():
    text = "Available September 2026. Rent is 3,800 ILS."

    assert parse_price_ils(text) == 3800


def test_strong_montefiore_match_sends():
    post = ApartmentPost(
        source="test",
        text=(
            "Montefiore room with roommates, renovated and bright, 3800 ILS, "
            "September 2026, Mamad inside, cafes nearby, 10 minutes walking."
        ),
    )

    result = score_post(post, Criteria())

    assert result.decision == Decision.SEND
    assert result.score >= 70
    assert result.price_ils == 3800
    assert result.shelter_signal == "mamad"


def test_no_mamad_no_shelter_is_major_negative():
    post = ApartmentPost(
        source="test",
        text=(
            "Tel Aviv apartment, old condition, 5200 ILS. "
            "No mamad and no shelter."
        ),
    )

    result = score_post(post, Criteria())

    assert result.decision == Decision.REJECT
    assert result.shelter_signal == "none"
    assert any("no Mamad and no shelter" in item for item in result.negatives)
