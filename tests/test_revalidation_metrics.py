import json
from datetime import UTC, datetime, timedelta

import pytest

from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.models import AnswerStatus, ReviewState, SourceDocument
from trustflow.domain.review import answer_state_digest


def _questionnaire(tmp_path, question: str):
    path = tmp_path / "questionnaire.json"
    path.write_text(json.dumps({"questions": [question]}), encoding="utf-8")
    return path


def _ingest_company_source(service, *, version: str, color: str) -> None:
    service.ingest_source(
        SourceDocument(
            id="company",
            title="Company profile",
            owner="trust",
            version=version,
            content=f"Our favorite color is {color}.",
            source_uri="policy://company/profile",
            updated_at=datetime.now(UTC),
            tags=frozenset({"favorite", "color", color}),
        )
    )


def test_revalidation_preserves_identity_and_requires_review_after_source_change(
    service,
    tmp_path,
) -> None:
    _ingest_company_source(service, version="1", color="blue")
    questionnaire = service.import_questionnaire(
        _questionnaire(tmp_path, "What is your favorite color?")
    )
    original = service.draft(questionnaire.id)[0]
    assert original.status is AnswerStatus.ANSWERED
    service.export(questionnaire.id, tmp_path / "before.json")
    first_draft_seconds = service.governance_metrics(questionnaire.id)[
        "time_to_first_draft_seconds"
    ]

    _ingest_company_source(service, version="2", color="green")
    scorecard_before = service.governance_metrics(questionnaire.id)
    assert scorecard_before["revalidation_required_answers"] == 1
    assert scorecard_before["current_evidence_rate"] == 0.0
    assert scorecard_before["external_claim_ready_rate"] == 0.0

    refreshed = service.revalidate(questionnaire.id)
    assert len(refreshed) == 1
    current = refreshed[0]
    assert current.id == original.id
    assert answer_state_digest(current) != answer_state_digest(original)
    assert current.status is AnswerStatus.REVIEW_REQUIRED
    assert "source_change_revalidation" in current.reasons
    assert current.evidence[0].source_version == "2"
    assert "green" in current.text.casefold()
    assert service.impact_scan("company") == []

    scorecard_pending = service.governance_metrics(questionnaire.id)
    assert scorecard_pending["revalidation_required_answers"] == 0
    assert scorecard_pending["current_evidence_rate"] == 1.0
    assert scorecard_pending["review_required_answers"] == 1
    assert scorecard_pending["review_completion_rate"] == 0.0
    assert scorecard_pending["external_claim_ready_rate"] == 0.0
    assert scorecard_pending["time_to_first_draft_seconds"] == first_draft_seconds

    with pytest.raises(InvalidTransitionError, match="missing_review"):
        service.export(questionnaire.id, tmp_path / "blocked.json")

    service.review(
        current.id,
        reviewer="trust-reviewer",
        state=ReviewState.APPROVED,
        final_text=current.text,
    )
    service.export(questionnaire.id, tmp_path / "after.json")
    scorecard_ready = service.governance_metrics(questionnaire.id)
    assert scorecard_ready["review_completion_rate"] == 1.0
    assert scorecard_ready["external_claim_ready_rate"] == 1.0
    assert scorecard_ready["external_claim_blocked_rate"] == 0.0
    assert scorecard_ready["reviewer_edit_rate"] == 0.0
    assert scorecard_ready["time_to_first_draft_seconds"] == first_draft_seconds
    assert scorecard_ready["median_review_turnaround_seconds"] >= 0.0

    revalidation_events = [
        item for item in service.store.list_audit() if item.event_type == "answer.revalidated"
    ]
    assert len(revalidation_events) == 1
    assert revalidation_events[0].entity_id == original.id
    assert revalidation_events[0].payload["changed_source_ids"] == ["company"]


def test_revalidation_preserves_review_history_but_expires_old_approval(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(
        _questionnaire(tmp_path, "Do you encrypt customer data at rest?")
    )
    original = service.draft(questionnaire.id)[0]
    assert original.status is AnswerStatus.REVIEW_REQUIRED
    old_review = service.review(
        original.id,
        reviewer="security-a",
        state=ReviewState.APPROVED,
        final_text=original.text,
    )

    source = service.store.get_source("security")
    assert source is not None
    service.ingest_source(
        source.model_copy(
            update={
                "version": "2",
                "content": "Customer data is encrypted at rest with AES-256.",
            }
        )
    )
    current = service.revalidate(questionnaire.id, source_id="security")[0]
    assert current.id == original.id
    assert service.review_history(current.id) == [old_review]

    with pytest.raises(InvalidTransitionError, match="review_state_changed"):
        service.export(questionnaire.id, tmp_path / "old-review-blocked.json")

    new_review = service.review(
        current.id,
        reviewer="security-b",
        state=ReviewState.APPROVED,
        final_text=current.text,
    )
    assert service.review_history(current.id) == [old_review, new_review]
    service.export(questionnaire.id, tmp_path / "fresh-review.json")


def test_review_rejects_source_drift_before_recording_approval(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(
        _questionnaire(tmp_path, "Do you encrypt customer data at rest?")
    )
    answer = service.draft(questionnaire.id)[0]
    source = service.store.get_source("security")
    assert source is not None
    service.ingest_source(source.model_copy(update={"version": "2"}))

    with pytest.raises(InvalidTransitionError, match="review blocked by invalid evidence") as exc:
        service.review(
            answer.id,
            reviewer="security",
            state=ReviewState.APPROVED,
            final_text=answer.text,
        )
    assert "source_version_changed" in str(exc.value)
    assert service.review_history(answer.id) == []


def test_source_filtered_revalidation_preserves_all_answer_level_impact_causes(
    service,
    tmp_path,
) -> None:
    service.ingest_source(
        SourceDocument(
            id="security-copy",
            title="Security implementation",
            owner="security",
            version="1",
            content="Customer data is encrypted at rest with AES-256.",
            source_uri="policy://security/copy",
            updated_at=datetime.now(UTC),
            tags=frozenset({"encrypt", "customer", "data", "rest", "aes-256"}),
        )
    )
    questionnaire = service.import_questionnaire(
        _questionnaire(tmp_path, "Do you encrypt customer data at rest?")
    )
    answer = service.draft(questionnaire.id)[0]
    assert {item.source_id for item in answer.evidence} >= {"security", "security-copy"}

    security = service.store.get_source("security")
    copy = service.store.get_source("security-copy")
    assert security is not None and copy is not None
    service.ingest_source(security.model_copy(update={"version": "2"}))
    service.ingest_source(copy.model_copy(update={"version": "2"}))

    refreshed = service.revalidate(questionnaire.id, source_id="security")
    assert len(refreshed) == 1
    event = next(
        item
        for item in reversed(service.store.list_audit())
        if item.event_type == "answer.revalidated"
    )
    assert event.payload["changed_source_ids"] == ["security", "security-copy"]


def test_stale_evidence_cannot_be_made_current_by_human_approval(service, tmp_path) -> None:
    source = service.store.get_source("security")
    assert source is not None
    service.ingest_source(
        source.model_copy(update={"updated_at": datetime.now(UTC) - timedelta(days=366)})
    )
    questionnaire = service.import_questionnaire(
        _questionnaire(tmp_path, "Do you encrypt customer data at rest?")
    )
    answer = service.draft(questionnaire.id)[0]
    assert answer.status is AnswerStatus.STALE

    for state in (ReviewState.APPROVED, ReviewState.EDITED):
        with pytest.raises(InvalidTransitionError, match="refreshed and revalidated"):
            service.review(
                answer.id,
                reviewer="security",
                state=state,
                final_text=(
                    answer.text if state is ReviewState.APPROVED else answer.text + " Confirmed."
                ),
            )

    with pytest.raises(InvalidTransitionError, match="stale_evidence"):
        service.export(questionnaire.id, tmp_path / "stale.json")


def test_revalidate_is_noop_without_current_impact(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(
        _questionnaire(tmp_path, "Do you encrypt customer data at rest?")
    )
    original = service.draft(questionnaire.id)[0]
    audit_count = len(service.store.list_audit())

    assert service.revalidate(questionnaire.id) == []
    assert service.store.get_answer(original.id) == original
    assert len(service.store.list_audit()) == audit_count
