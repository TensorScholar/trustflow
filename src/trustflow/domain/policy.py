"""Answer policy and conflict detection."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from trustflow.domain.models import (
    AnswerStatus,
    Evidence,
    PolicySettings,
    QuestionSensitivity,
)

_NEGATION = re.compile(r"\b(no|not|never|does not|do not|cannot|can't)\b", re.IGNORECASE)


def evidence_conflicts(evidence: tuple[Evidence, ...]) -> bool:
    if len(evidence) < 2:
        return False
    polarities = {_NEGATION.search(item.excerpt) is not None for item in evidence[:3]}
    return len(polarities) > 1


def decide_status(
    *,
    confidence: float,
    evidence: tuple[Evidence, ...],
    sensitivity: QuestionSensitivity,
    policy: PolicySettings,
    now: datetime | None = None,
) -> tuple[AnswerStatus, tuple[str, ...]]:
    current_time = now or datetime.now(UTC)
    if not evidence:
        return AnswerStatus.UNANSWERABLE, ("no_approved_evidence",)
    if any(item.valid_until is not None and item.valid_until <= current_time for item in evidence):
        return AnswerStatus.STALE, ("source_expired",)
    if any(
        max(0, (current_time - item.updated_at).days) > policy.maximum_source_age_days
        for item in evidence
    ):
        return AnswerStatus.STALE, ("source_age_exceeded",)
    if evidence_conflicts(evidence):
        return AnswerStatus.CONFLICT, ("sources_conflict",)
    if confidence < policy.minimum_answer_confidence:
        return AnswerStatus.REVIEW_REQUIRED, ("low_confidence",)
    if policy.sensitive_requires_review and sensitivity is not QuestionSensitivity.STANDARD:
        return AnswerStatus.REVIEW_REQUIRED, ("sensitive_question",)
    return AnswerStatus.ANSWERED, ("evidence_threshold_met",)
