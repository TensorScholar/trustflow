import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.evidence import (
    evidence_invalidation_reason,
    source_provenance_digest,
)
from trustflow.domain.models import (
    Evidence,
    PolicySettings,
    ReviewState,
    SourceClassification,
    SourceDocument,
)
from trustflow.domain.retrieval import retrieve


def _source() -> SourceDocument:
    return SourceDocument(
        id="security",
        title="Security policy",
        owner="security",
        version="1",
        content="Customer data is encrypted at rest with AES-256.",
        source_uri="policy://security",
        classification=SourceClassification.INTERNAL,
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        tags=frozenset({"security", "encryption"}),
    )


def _snapshot(source: SourceDocument) -> Evidence:
    items = retrieve(
        "Do you encrypt customer data at rest?",
        [source],
        PolicySettings(minimum_evidence_score=0.1),
    )
    assert len(items) == 1
    return items[0]


def test_retrieval_snapshots_source_provenance() -> None:
    source = _source()
    evidence = _snapshot(source)
    assert evidence.source_provenance_digest == source_provenance_digest(source)
    assert evidence.source_provenance_digest != "0" * 64


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Renamed security policy"),
        ("owner", "governance"),
        ("source_uri", "policy://security/v2"),
        ("classification", SourceClassification.CONFIDENTIAL),
        ("tags", frozenset({"security", "encryption", "restricted"})),
        ("updated_at", datetime(2026, 1, 2, tzinfo=UTC)),
        ("valid_until", datetime(2027, 1, 1, tzinfo=UTC)),
    ],
)
def test_provenance_metadata_drift_invalidates_snapshot(field: str, value: object) -> None:
    source = _source()
    evidence = _snapshot(source)
    changed = source.model_copy(update={field: value})
    reason = evidence_invalidation_reason(
        changed,
        evidence,
        PolicySettings(maximum_source_age_days=1000),
        now=datetime(2026, 1, 3, tzinfo=UTC),
    )
    assert reason == "source_provenance_changed"


def test_specific_source_change_reasons_precede_provenance_reason() -> None:
    source = _source()
    evidence = _snapshot(source)
    policy = PolicySettings(maximum_source_age_days=1000)
    now = datetime(2026, 1, 3, tzinfo=UTC)

    assert (
        evidence_invalidation_reason(
            source.model_copy(update={"approved": False}), evidence, policy, now=now
        )
        == "source_revoked"
    )
    assert (
        evidence_invalidation_reason(
            source.model_copy(update={"version": "2"}), evidence, policy, now=now
        )
        == "source_version_changed"
    )
    assert (
        evidence_invalidation_reason(
            source.model_copy(update={"content": source.content + " Updated."}),
            evidence,
            policy,
            now=now,
        )
        == "source_content_changed"
    )


def test_legacy_snapshot_without_provenance_digest_fails_closed() -> None:
    source = _source()
    evidence = _snapshot(source).model_copy(update={"source_provenance_digest": "0" * 64})
    assert (
        evidence_invalidation_reason(
            source,
            evidence,
            PolicySettings(maximum_source_age_days=1000),
            now=datetime(2026, 1, 3, tzinfo=UTC),
        )
        == "source_snapshot_missing"
    )


def test_source_update_reports_reviewed_impact_and_blocks_export(service, tmp_path) -> None:
    questionnaire_path = tmp_path / "questionnaire.json"
    questionnaire_path.write_text(
        json.dumps({"questions": ["Do you encrypt customer data at rest?"]}),
        encoding="utf-8",
    )
    questionnaire = service.import_questionnaire(questionnaire_path)
    answer = service.draft(questionnaire.id)[0]
    review = service.review(
        answer.id,
        reviewer="security-reviewer",
        state=ReviewState.APPROVED,
        final_text=answer.text,
    )

    current = service.store.get_source("security")
    assert current is not None
    service.ingest_source(current.model_copy(update={"owner": "governance"}))

    findings = service.impact_scan("security")
    assert len(findings) == 1
    finding = findings[0]
    assert finding.questionnaire_id == questionnaire.id
    assert finding.answer_id == answer.id
    assert finding.review_id == review.id
    assert finding.review_state is ReviewState.APPROVED
    assert finding.reason == "source_provenance_changed"
    assert service.impact_scan("unrelated") == []

    source_event = service.store.list_audit()[-1]
    assert source_event.event_type == "source.ingested"
    assert source_event.payload["replaced"] is True
    assert source_event.payload["impact_count"] == 1

    with pytest.raises(InvalidTransitionError, match="source_provenance_changed"):
        service.export(questionnaire.id, tmp_path / "blocked.json")


def test_provenance_digest_is_stable_for_identical_source() -> None:
    source = _source()
    assert source_provenance_digest(source) == source_provenance_digest(source.model_copy())


def test_equivalent_timezone_offsets_have_same_provenance_digest() -> None:
    source = _source()
    same_instant = source.updated_at.astimezone(timezone(timedelta(hours=3, minutes=30)))
    shifted = source.model_copy(update={"updated_at": same_instant})
    assert source_provenance_digest(source) == source_provenance_digest(shifted)


def test_provenance_digest_changes_when_freshness_is_extended() -> None:
    source = _source()
    refreshed = source.model_copy(update={"updated_at": source.updated_at + timedelta(days=1)})
    assert source_provenance_digest(source) != source_provenance_digest(refreshed)
