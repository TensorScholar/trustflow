from trustflow.adapters.sqlite import SQLiteStore
from trustflow.domain.audit import make_event
from trustflow.domain.models import (
    AnswerStatus,
    DocumentFormat,
    DraftAnswer,
    Questionnaire,
    Question,
    QuestionLocation,
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
    assert store.list_audit() == [event]
