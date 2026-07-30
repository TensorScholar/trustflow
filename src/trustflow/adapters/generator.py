"""Offline, evidence-only answer generator."""

from trustflow.domain.models import Evidence


class ExtractiveAnswerGenerator:
    def generate(
        self,
        *,
        question: str,
        evidence: tuple[object, ...],
    ) -> tuple[str, float]:
        typed = tuple(item for item in evidence if isinstance(item, Evidence))
        if not typed:
            return "No approved evidence is available. Human input is required.", 0.0
        primary = typed[0]
        answer = primary.excerpt
        confidence = min(0.96, 0.62 + sum(item.score for item in typed[:2]) / 3)
        return answer, confidence
