from apartment_search.models import ApartmentPost, Criteria
from apartment_search.scoring import score_post
from apartment_search.storage import SeenStore


def test_seen_store_marks_post(tmp_path):
    post = ApartmentPost(source="test", text="Montefiore room 3800 ILS")
    score = score_post(post, Criteria())

    with SeenStore(tmp_path / "seen.sqlite3") as store:
        assert not store.has_seen(post)
        store.mark_seen(post, score)
        assert store.has_seen(post)
