"""Deterministic review-to-answer binding."""

from __future__ import annotations

import hashlib
import json
import re

from trustflow.domain.models import DraftAnswer, ReviewDecision, ReviewState

MISSING_ANSWER_DIGEST = "0" * 64
_WHITESPACE = re.compile(r"\s+")


def answer_state_digest(answer: DraftAnswer) -> str:
    """Fingerprint the exact draft and evidence snapshot presented for review."""
    payload = json.dumps(
        answer.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized_claim_text(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip().casefold()


def edited_text_support_error(answer: DraftAnswer, final_text: str) -> str | None:
    """Fail closed when a human edit is not bound verbatim to retained evidence.

    Pre-1.0 TrustFlow does not claim semantic verification of arbitrary human prose. An edited
    external claim must therefore correspond, modulo case/whitespace, to one complete retained
    evidence excerpt. This permits selecting a different evidence-backed wording without allowing
    an edit to silently add or remove qualifiers from the source text.
    """
    if not answer.evidence:
        return "edited_text_without_evidence"
    candidate = _normalized_claim_text(final_text)
    evidence_texts = {_normalized_claim_text(item.excerpt) for item in answer.evidence}
    if candidate not in evidence_texts:
        return "edited_text_not_evidence_bound"
    return None


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
    if review.state is ReviewState.EDITED:
        if review.final_text == answer.text:
            return "edited_text_unchanged"
        support_error = edited_text_support_error(answer, review.final_text)
        if support_error is not None:
            return support_error
    return None
