import json

import pytest

from trustflow.domain.errors import InvalidTransitionError, NotFoundError
from trustflow.domain.models import AnswerStatus, ReviewState, SourceDocument


def questionnaire_file(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(
            {
                "questions": [
                    "Do you encrypt customer data at rest?",
                    "What are your indemnity terms?",
                    "What is your favorite color?",
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_end_to_end(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    answers = service.draft(questionnaire.id)
    statuses = {item.status for item in answers}
    assert AnswerStatus.REVIEW_REQUIRED in statuses
    assert AnswerStatus.UNANSWERABLE in statuses
    for answer in answers:
        if answer.status is AnswerStatus.UNANSWERABLE:
            service.review(
                answer.id,
                reviewer="human",
                state=ReviewState.EDITED,
                final_text="Not applicable.",
            )
        elif answer.status is not AnswerStatus.ANSWERED:
            service.review(
                answer.id,
                reviewer="human",
                state=ReviewState.APPROVED,
                final_text=answer.text,
            )
    output = tmp_path / "completed.json"
    result = service.export(questionnaire.id, output)
    assert output.exists()
    assert result.questionnaire_id == questionnaire.id


def test_review(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    review = service.review(
        answer.id,
        reviewer="security@example.com",
        state=ReviewState.EDITED,
        final_text="Yes. Customer data is encrypted at rest with AES-256.",
    )
    assert review.final_text.startswith("Yes")


def test_unanswerable_cannot_be_approved_without_edit(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    answer = service.draft(questionnaire.id)[-1]
    assert answer.status is AnswerStatus.UNANSWERABLE
    with pytest.raises(InvalidTransitionError):
        service.review(
            answer.id,
            reviewer="r",
            state=ReviewState.APPROVED,
            final_text="No approved evidence is available. Human input is required.",
        )


def test_missing_questionnaire(service) -> None:
    with pytest.raises(NotFoundError):
        service.draft("missing")


def test_export_before_draft_fails(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    with pytest.raises(InvalidTransitionError):
        service.export(questionnaire.id, tmp_path / "out.json")


def test_impact_scan(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    service.draft(questionnaire.id)
    existing = service.store.get_source("security")
    assert existing is not None
    service.ingest_source(existing.model_copy(update={"version": "2"}))
    findings = service.impact_scan()
    assert any(item.source_id == "security" for item in findings)


def test_export_blocks_unreviewed_answers(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    service.draft(questionnaire.id)
    with pytest.raises(InvalidTransitionError, match="missing_review"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_export_blocks_rejected_review(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    service.review(
        answer.id,
        reviewer="security",
        state=ReviewState.REJECTED,
        note="Evidence is insufficient.",
    )
    with pytest.raises(InvalidTransitionError, match="rejected"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_draft_is_not_duplicated(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    service.draft(questionnaire.id)
    with pytest.raises(InvalidTransitionError, match="already been drafted"):
        service.draft(questionnaire.id)


def test_metrics_requires_questionnaire(service) -> None:
    with pytest.raises(NotFoundError, match="questionnaire not found"):
        service.metrics("missing")
