from datetime import UTC, datetime, timedelta

from trustflow.domain.models import (
    AnswerStatus,
    ApplicabilityScope,
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


def test_scoped_question_without_applicable_evidence_is_explicit() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
        question="Does the OnPrem product encrypt customer data at rest?",
    )
    assert status is AnswerStatus.UNANSWERABLE
    assert reasons == ("no_applicable_evidence",)


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


def test_unknown_declared_region_scope_requires_review() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(evidence("Customer data is encrypted at rest."),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
        question="Is customer data in the US region encrypted at rest?",
    )
    assert status is AnswerStatus.REVIEW_REQUIRED
    assert reasons == ("applicability_unknown:region",)


def test_matching_declared_region_scope_can_answer() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(
            evidence(
                "Customer data in the US region is encrypted at rest.",
                applicability=ApplicabilityScope(regions=frozenset({"us"})),
            ),
        ),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
        question="Is customer data in the US region encrypted at rest?",
    )
    assert status is AnswerStatus.ANSWERED
    assert reasons == ("evidence_threshold_met",)


def test_partial_conjunctive_support_requires_review() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(evidence("Customer files are encrypted at rest."),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
        question="Are customer files encrypted both at rest and in transit?",
    )
    assert status is AnswerStatus.REVIEW_REQUIRED
    assert "partial_support_risk" in reasons


def test_universal_claim_requires_matching_universal_evidence() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(evidence("Production databases are encrypted at rest."),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
        question="Is all customer data encrypted everywhere?",
    )
    assert status is AnswerStatus.REVIEW_REQUIRED
    assert "overbroad_claim_risk" in reasons


def test_broad_security_predicate_requires_review() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(evidence("Customer data is encrypted at rest."),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
        question="Is customer data secure?",
    )
    assert status is AnswerStatus.REVIEW_REQUIRED
    assert "ambiguous_claim_risk" in reasons


def test_internally_contradictory_question_requires_review() -> None:
    status, reasons = decide_status(
        confidence=1,
        evidence=(evidence("Customer data is encrypted at rest."),),
        sensitivity=QuestionSensitivity.STANDARD,
        policy=PolicySettings(),
        question=(
            "Do you encrypt customer data at rest while also not encrypting customer data at rest?"
        ),
    )
    assert status is AnswerStatus.REVIEW_REQUIRED
    assert "contradictory_claim_risk" in reasons
