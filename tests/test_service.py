import json
from datetime import UTC, datetime, timedelta

import pytest

from trustflow.domain.errors import InvalidTransitionError, NotFoundError
from trustflow.domain.models import (
    AnswerStatus,
    ReviewDecision,
    ReviewState,
    SourceDocument,
)
from trustflow.domain.review import answer_state_digest


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


def single_security_questionnaire(tmp_path):
    path = tmp_path / "security-question.json"
    path.write_text(
        json.dumps({"questions": ["Do you encrypt customer data at rest?"]}),
        encoding="utf-8",
    )
    return path


def test_end_to_end(service, tmp_path) -> None:
    service.ingest_source(
        SourceDocument(
            id="company",
            title="Company profile",
            owner="trust",
            version="1",
            content="Our favorite color is blue.",
            source_uri="policy://company",
            updated_at=datetime.now(UTC),
        )
    )
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    answers = service.draft(questionnaire.id)
    statuses = {item.status for item in answers}
    assert AnswerStatus.REVIEW_REQUIRED in statuses
    assert AnswerStatus.UNANSWERABLE not in statuses
    for answer in answers:
        if answer.status is not AnswerStatus.ANSWERED:
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
    assert review.answer_digest == answer_state_digest(answer)


def test_approved_review_must_preserve_exact_draft(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    with pytest.raises(InvalidTransitionError, match="preserve the exact draft"):
        service.review(
            answer.id,
            reviewer="security",
            state=ReviewState.APPROVED,
            final_text=answer.text + " Expanded.",
        )


def test_edited_review_must_actually_change_text(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    with pytest.raises(InvalidTransitionError, match="changed final text"):
        service.review(
            answer.id,
            reviewer="security",
            state=ReviewState.EDITED,
            final_text=answer.text,
        )


def test_review_replay_is_blocked_after_answer_state_changes(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    service.review(
        answer.id,
        reviewer="security",
        state=ReviewState.APPROVED,
        final_text=answer.text,
    )
    service.store.put_answer(answer.model_copy(update={"reasons": (*answer.reasons, "mutated")}))

    with pytest.raises(InvalidTransitionError, match="review_state_changed"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_legacy_unbound_review_is_not_trusted(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    service.store.put_review(
        ReviewDecision(
            answer_id=answer.id,
            reviewer="legacy-label",
            state=ReviewState.APPROVED,
            final_text=answer.text,
        )
    )

    with pytest.raises(InvalidTransitionError, match="review_unbound"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_review_history_is_append_only_and_latest_decision_governs(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    rejected = service.review(
        answer.id,
        reviewer="security-a",
        state=ReviewState.REJECTED,
        note="Needs another pass.",
    )
    approved = service.review(
        answer.id,
        reviewer="security-b",
        state=ReviewState.APPROVED,
        final_text=answer.text,
    )

    assert service.review_history(answer.id) == [rejected, approved]
    result = service.export(questionnaire.id, tmp_path / "approved.json")
    assert result.questionnaire_id == questionnaire.id


def test_unanswerable_cannot_be_promoted_to_external_claim(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    answer = service.draft(questionnaire.id)[-1]
    assert answer.status is AnswerStatus.UNANSWERABLE
    for state in (ReviewState.APPROVED, ReviewState.EDITED):
        with pytest.raises(InvalidTransitionError, match="no approved evidence"):
            service.review(
                answer.id,
                reviewer="r",
                state=state,
                final_text="Not applicable.",
            )


def test_missing_questionnaire(service) -> None:
    with pytest.raises(NotFoundError):
        service.draft("missing")


def test_missing_answer_review_history(service) -> None:
    with pytest.raises(NotFoundError, match="answer not found"):
        service.review_history("missing")


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
    assert any(
        item.source_id == "security" and item.reason == "source_version_changed"
        for item in findings
    )


def test_impact_scan_detects_same_version_content_mutation(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    service.draft(questionnaire.id)
    existing = service.store.get_source("security")
    assert existing is not None
    service.ingest_source(existing.model_copy(update={"content": existing.content + " Updated."}))
    findings = service.impact_scan()
    assert any(
        item.source_id == "security" and item.reason == "source_content_changed"
        for item in findings
    )


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


def test_export_revalidates_source_version_after_review(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    service.review(
        answer.id,
        reviewer="security",
        state=ReviewState.APPROVED,
        final_text=answer.text,
    )
    existing = service.store.get_source("security")
    assert existing is not None
    service.ingest_source(existing.model_copy(update={"version": "2"}))
    with pytest.raises(InvalidTransitionError, match="source_version_changed"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_export_revalidates_same_version_source_content(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    service.review(
        answer.id,
        reviewer="security",
        state=ReviewState.APPROVED,
        final_text=answer.text,
    )
    existing = service.store.get_source("security")
    assert existing is not None
    service.ingest_source(existing.model_copy(update={"content": existing.content + " Updated."}))
    with pytest.raises(InvalidTransitionError, match="source_content_changed"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_export_blocks_revoked_source_after_review(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    service.review(
        answer.id,
        reviewer="security",
        state=ReviewState.APPROVED,
        final_text=answer.text,
    )
    existing = service.store.get_source("security")
    assert existing is not None
    service.ingest_source(existing.model_copy(update={"approved": False}))
    with pytest.raises(InvalidTransitionError, match="source_revoked"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_export_blocks_source_that_ages_out_after_review(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(single_security_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    service.review(
        answer.id,
        reviewer="security",
        state=ReviewState.APPROVED,
        final_text=answer.text,
    )
    existing = service.store.get_source("security")
    assert existing is not None
    service.ingest_source(
        existing.model_copy(update={"updated_at": datetime.now(UTC) - timedelta(days=366)})
    )
    with pytest.raises(InvalidTransitionError, match="source_too_old"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_draft_is_not_duplicated(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(questionnaire_file(tmp_path))
    service.draft(questionnaire.id)
    with pytest.raises(InvalidTransitionError, match="already been drafted"):
        service.draft(questionnaire.id)


def test_metrics_requires_questionnaire(service) -> None:
    with pytest.raises(NotFoundError, match="questionnaire not found"):
        service.metrics("missing")
