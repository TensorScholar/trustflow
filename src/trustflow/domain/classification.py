"""Deterministic question sensitivity classification."""

from trustflow.domain.models import QuestionSensitivity


def classify_sensitivity(text: str) -> QuestionSensitivity:
    normalized = text.casefold()
    if any(term in normalized for term in ("gdpr", "privacy", "personal data", "data subject")):
        return QuestionSensitivity.PRIVACY
    if any(term in normalized for term in ("indemnity", "liability", "contract", "legal")):
        return QuestionSensitivity.LEGAL
    if any(
        term in normalized
        for term in ("soc 2", "iso 27001", "encrypt", "penetration test", "security")
    ):
        return QuestionSensitivity.SECURITY
    if any(term in normalized for term in ("revenue", "financial", "insurance", "credit")):
        return QuestionSensitivity.FINANCIAL
    return QuestionSensitivity.STANDARD
