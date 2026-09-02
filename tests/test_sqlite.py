import json
import sqlite3
from datetime import UTC, datetime

import pytest

from trustflow.adapters.sqlite import SQLiteStore
from trustflow.domain.audit import make_event
from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.models import (
    AnswerStatus,
    DocumentFormat,
    DraftAnswer,
    Question,
    QuestionLocation,
    Questionnaire,
    ReviewDecision,
    ReviewState,
    SourceDocument,
)


def test_sqlite_roundtrip(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "trustflow.db")
    source = SourceDocument(
        id="s",
        title="S",
        owner="o",
        version="1",
        content="content",
        source_uri="p://s",
    )
    question = Question(
        id="q",
        text="Question?",
        location=QuestionLocation(format=DocumentFormat.JSON, key="0"),
    )
    questionnaire = Questionnaire(
        id="n",
        title="N",
        source_path="n.json",
        format=DocumentFormat.JSON,
        questions=(question,),
    )
    answer = DraftAnswer(
        id="a",
        questionnaire_id="n",
        question_id="q",
        text="A",
        status=AnswerStatus.ANSWERED,
        confidence=1,
    )
    review = ReviewDecision(
        answer_id="a",
        reviewer="r",
        state=ReviewState.APPROVED,
        final_text="A",
    )
    event = make_event(
        sequence=1,
        event_type="x",
        entity_id="x",
        payload={},
        previous_hash="0" * 64,
    )
    store.put_source(source)
    store.put_questionnaire(questionnaire)
    store.put_answer(answer)
    store.put_review(review)
    store.append_audit(event)
    assert store.get_source("s") == source
    assert store.list_sources() == [source]
    assert store.get_questionnaire("n") == questionnaire
    assert store.get_answer("a") == answer
    assert store.list_answers("n") == [answer]
    assert store.get_review_for_answer("a") == review
    assert store.list_reviews_for_answer("a") == [review]
    assert store.list_audit() == [event]


def test_sqlite_review_history_is_append_only(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "reviews.db")
    first = ReviewDecision(
        id="r1",
        answer_id="a",
        reviewer="one",
        state=ReviewState.REJECTED,
    )
    second = ReviewDecision(
        id="r2",
        answer_id="a",
        reviewer="two",
        state=ReviewState.APPROVED,
        final_text="A",
    )
    store.put_review(first)
    store.put_review(second)

    assert store.list_reviews_for_answer("a") == [first, second]
    assert store.get_review_for_answer("a") == second
    with pytest.raises(InvalidTransitionError, match="already exists"):
        store.put_review(second)


def test_sqlite_migrates_legacy_single_review_as_unbound_history(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    created_at = datetime.now(UTC).isoformat()
    legacy_payload = json.dumps(
        {
            "id": "legacy-review",
            "answer_id": "a",
            "reviewer": "legacy-label",
            "state": "approved",
            "final_text": "A",
            "note": "",
            "created_at": created_at,
        }
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE reviews(answer_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO reviews(answer_id,payload) VALUES(?,?)",
            ("a", legacy_payload),
        )

    store = SQLiteStore(path)
    history = store.list_reviews_for_answer("a")
    assert len(history) == 1
    assert history[0].id == "legacy-review"
    assert history[0].answer_digest == "0" * 64


def test_concurrent_audit_appends_are_serialized(tmp_path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from trustflow.domain.audit import verify_chain

    path = tmp_path / "concurrent.db"
    store = SQLiteStore(path)

    def append(index: int) -> None:
        SQLiteStore(path).append_audit_event("test.concurrent", str(index), {"index": index})

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, range(40)))

    events = store.list_audit()
    assert len(events) == 40
    verify_chain(events)
