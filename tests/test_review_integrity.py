from datetime import UTC, datetime

import pytest

from trustflow.adapters.exporters import ExporterRegistry
from trustflow.adapters.parsers import ParserRegistry
from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.models import (
    AnswerStatus,
    DraftAnswer,
    Evidence,
    ReviewDecision,
    ReviewState,
)
from trustflow.domain.review import answer_state_digest


def governed_answer(questionnaire_id: str) -> DraftAnswer:
    return DraftAnswer(
        id="answer",
        questionnaire_id=questionnaire_id,
        question_id="q1",
        text="Approved evidence.",
        status=AnswerStatus.REVIEW_REQUIRED,
        confidence=1,
        evidence=(
            Evidence(
                source_id="source",
                source_title="Source",
                source_uri="policy://source",
                source_version="1",
                source_digest="a" * 64,
                owner="security",
                excerpt="Approved evidence.",
                score=1,
                updated_at=datetime.now(UTC),
            ),
        ),
    )


def test_exporter_rejects_review_replay_on_mutated_answer(tmp_path) -> None:
    source = tmp_path / "q.json"
    source.write_text('{"questions":["Question?"]}', encoding="utf-8")
    questionnaire = ParserRegistry().parse(source)
    answer = governed_answer(questionnaire.id)
    review = ReviewDecision(
        answer_id=answer.id,
        answer_digest=answer_state_digest(answer),
        reviewer="security-label",
        state=ReviewState.APPROVED,
        final_text=answer.text,
    )
    mutated = answer.model_copy(update={"reasons": ("changed-after-review",)})

    with pytest.raises(InvalidTransitionError, match="review_state_changed"):
        ExporterRegistry().export(
            questionnaire,
            [mutated],
            {answer.id: review},
            tmp_path / "blocked.json",
        )


def test_exporter_rejects_approved_text_not_equal_to_reviewed_draft(tmp_path) -> None:
    source = tmp_path / "q.json"
    source.write_text('{"questions":["Question?"]}', encoding="utf-8")
    questionnaire = ParserRegistry().parse(source)
    answer = governed_answer(questionnaire.id)
    review = ReviewDecision(
        answer_id=answer.id,
        answer_digest=answer_state_digest(answer),
        reviewer="security-label",
        state=ReviewState.APPROVED,
        final_text="Broader external claim.",
    )

    with pytest.raises(InvalidTransitionError, match="approved_text_mismatch"):
        ExporterRegistry().export(
            questionnaire,
            [answer],
            {answer.id: review},
            tmp_path / "blocked.json",
        )
