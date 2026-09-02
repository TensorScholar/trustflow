from datetime import UTC, datetime, timedelta

from trustflow.domain.models import (
    AnswerStatus,
    Evidence,
    PolicySettings,
    QuestionSensitivity,
)
from trustflow.domain.policy import decide_status, evidence_conflicts


def evidence(text: str, source_id: str = "s", **kwargs) -> Evidence:
    return Evidence(
        source_id=source_id,
        source_title=source_id,
        source_uri=f"p://{source_id}",
        source_version="1",
        owner="o",
        excerpt=text,
        score=0.8,
        updated_at=kwargs.pop("updated_at", datetime.now(UTC)),
        **kwargs,
    )


def test_no_evidence_unanswerable() -> None:
    status, _ = decide_status(
        confidence=1,
        evidence=(),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
    )
    assert status is AnswerStatus.UNANSWERABLE


def test_sensitive_requires_review() -> None:
    status, _ = decide_status(
        confidence=1,
        evidence=(evidence("We encrypt data."),),
        sensitivity=QuestionSensitivity.SECURITY,
        policy=PolicySettings(),
    )
    assert status is AnswerStatus.REVIEW_REQUIRED


def test_standard_answered() -> None:
    status, _ = decide_status(
        confidence=1,
        evidence=(evidence("We operate in the US."),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
    )
    assert status is AnswerStatus.ANSWERED


def test_expired_evidence_is_stale() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(evidence("Evidence", valid_until=datetime.now(UTC) - timedelta(seconds=1)),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
    )
    assert status is AnswerStatus.STALE
    assert reasons == ("source_expired",)


def test_old_evidence_is_stale() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(evidence("Evidence", updated_at=datetime.now(UTC) - timedelta(days=31)),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(maximum_source_age_days=30),
    )
    assert status is AnswerStatus.STALE
    assert reasons == ("source_age_exceeded",)


def test_conflict() -> None:
    items = (evidence("We encrypt data.", "a"), evidence("We do not encrypt data.", "b"))
    assert evidence_conflicts(items)
    status, _ = decide_status(
        confidence=1,
        evidence=items,
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
    )
    assert status is AnswerStatus.CONFLICT


def test_low_confidence_review() -> None:
    status, _ = decide_status(
        confidence=0.1,
        evidence=(evidence("Evidence"),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
    )
    assert status is AnswerStatus.REVIEW_REQUIRED
