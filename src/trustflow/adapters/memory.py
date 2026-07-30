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
        self.audit: list[AuditEvent] = []

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
        self.reviews[review.answer_id] = review

    def get_review_for_answer(self, answer_id: str) -> ReviewDecision | None:
        return self.reviews.get(answer_id)

    def append_audit(self, event: AuditEvent) -> None:
        self.audit.append(event)

    def list_audit(self) -> list[AuditEvent]:
        return list(self.audit)
