"""Self-introductions set the asker's region and are cut out of the search text; topics stay topics."""
import uuid

import pytest

from app.services.locality import detect, promote
from app.services.normalize import question_to_keywords


@pytest.mark.parametrize(
    "question, region, keywords",
    [
        ("Hey, I'm a student from St. Mary University, I want to learn about Black Loyalists", "nova-scotia", "Black Loyalists"),
        ("Hi I'm a student at Saint Mary's University and I need to learn more about Black churches", "nova-scotia", "Black churches"),
        ("I'm a student from Nova Scotia. What happened to Africville?", "nova-scotia", "Africville"),
        ("I'm a grade 10 student in Halifax researching the Book of Negroes", "nova-scotia", "Book of Negroes"),
        ("I'm from Toronto, tell me about Mary Ann Shadd", "ontario", "Mary Ann Shadd"),
        ("je suis étudiante à Montréal, parle-moi des Loyalistes noirs", "quebec", "Loyalistes noirs"),
    ],
)
def test_self_introduction_sets_region_and_is_removed(question, region, keywords):
    r, rest = detect(question)
    assert r is not None and r.key == region
    assert question_to_keywords(rest) == keywords


def test_topic_place_sets_region_but_stays_in_query():
    r, rest = detect("Black churches in Nova Scotia")
    assert r is not None and r.key == "nova-scotia"
    assert rest == "Black churches in Nova Scotia"
    r, rest = detect("I'm interested in Halifax history")
    assert r is not None and rest == "I'm interested in Halifax history"  # interest is the topic, not where they are


def test_no_region_for_plain_or_destination_questions():
    assert detect("Book of Negroes")[0] is None
    assert detect("Underground Railroad to Canada")[0] is None  # Canada as a destination is a topic


def test_promote_orders_held_then_about_then_rest_within_window():
    ids = [uuid.uuid4() for _ in range(6)]
    tiers = {ids[4]: 0, ids[2]: 1, ids[5]: 0}
    out = promote(ids, tiers, window=5, id_of=lambda x: x)
    assert out == [ids[4], ids[2], ids[0], ids[1], ids[3], ids[5]]  # ids[5] is past the window: untouched
