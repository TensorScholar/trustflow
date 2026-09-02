"""Deterministic review-to-answer binding."""

from __future__ import annotations

import hashlib
import json

from trustflow.domain.models import DraftAnswer, ReviewDecision, ReviewState

MISSING_ANSWER_DIGEST = "0" * 64


def answer_state_digest(answer: DraftAnswer) -> str:
    """Fingerprint the exact draft and evidence snapshot presented for review."""
    payload = json.dumps(
        answer.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def review_binding_error(answer: DraftAnswer, review: ReviewDecision) -> str | None:
    """Return a stable fail-closed reason when a review does not bind to this answer."""
    if review.answer_id != answer.id:
        return "review_answer_mismatch"
    if review.answer_digest == MISSING_ANSWER_DIGEST:
        return "review_unbound"
    if review.answer_digest != answer_state_digest(answer):
        return "review_state_changed"
    if review.state is ReviewState.APPROVED and review.final_text != answer.text:
        return "approved_text_mismatch"
    if review.state is ReviewState.EDITED and review.final_text == answer.text:
        return "edited_text_unchanged"
    return None
