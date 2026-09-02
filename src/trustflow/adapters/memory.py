from __future__ import annotations

from threading import Lock

from trustflow.domain.audit import make_event
from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.models import (
    AuditEvent,
    DraftAnswer,
    Questionnaire,
    ReviewDecision,
    SourceDocument,
)


class MemoryStore:
    def __init__(self) -> None:
        self.sources: dict[str, SourceDocument] = {}
        self.questionnaires: dict[str, Questionnaire] = {}
        self.answers: dict[str, DraftAnswer] = {}
        self.reviews: dict[str, ReviewDecision] = {}
        self._review_order: list[str] = []
        self.audit: list[AuditEvent] = []
        self._audit_lock = Lock()

    def put_source(self, source: SourceDocument) -> None:
        self.sources[source.id] = source

    def get_source(self, source_id: str) -> SourceDocument | None:
        return self.sources.get(source_id)

    def list_sources(self) -> list[SourceDocument]:
        return list(self.sources.values())

    def put_questionnaire(self, questionnaire: Questionnaire) -> None:
        self.questionnaires[questionnaire.id] = questionnaire

    def get_questionnaire(self, questionnaire_id: str) -> Questionnaire | None:
        return self.questionnaires.get(questionnaire_id)

    def put_answer(self, answer: DraftAnswer) -> None:
        self.answers[answer.id] = answer

    def get_answer(self, answer_id: str) -> DraftAnswer | None:
        return self.answers.get(answer_id)

    def list_answers(self, questionnaire_id: str | None = None) -> list[DraftAnswer]:
        answers = list(self.answers.values())
        if questionnaire_id is not None:
            answers = [item for item in answers if item.questionnaire_id == questionnaire_id]
        return answers

    def put_review(self, review: ReviewDecision) -> None:
        if review.id in self.reviews:
            raise InvalidTransitionError(f"review decision already exists: {review.id}")
        self.reviews[review.id] = review
        self._review_order.append(review.id)

    def get_review_for_answer(self, answer_id: str) -> ReviewDecision | None:
        history = self.list_reviews_for_answer(answer_id)
        return history[-1] if history else None

    def list_reviews_for_answer(self, answer_id: str) -> list[ReviewDecision]:
        return [
            self.reviews[review_id]
            for review_id in self._review_order
            if self.reviews[review_id].answer_id == answer_id
        ]

    def append_audit(self, event: AuditEvent) -> None:
        with self._audit_lock:
            self.audit.append(event)

    def append_audit_event(
        self,
        event_type: str,
        entity_id: str,
        payload: dict[str, object],
    ) -> AuditEvent:
        with self._audit_lock:
            previous = self.audit[-1].event_hash if self.audit else "0" * 64
            event = make_event(
                sequence=len(self.audit) + 1,
                event_type=event_type,
                entity_id=entity_id,
                payload=payload,
                previous_hash=previous,
            )
            self.audit.append(event)
            return event

    def list_audit(self) -> list[AuditEvent]:
        with self._audit_lock:
            return list(self.audit)
