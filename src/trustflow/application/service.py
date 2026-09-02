from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from trustflow.domain.audit import verify_chain
from trustflow.domain.errors import InvalidTransitionError, NotFoundError
from trustflow.domain.evidence import evidence_invalidation_reason
from trustflow.domain.models import (
    AnswerStatus,
    DraftAnswer,
    EvaluationCase,
    EvaluationSummary,
    ExportResult,
    ImpactFinding,
    PolicySettings,
    Questionnaire,
    ReviewDecision,
    ReviewState,
    SourceDocument,
)
from trustflow.domain.policy import decide_status
from trustflow.domain.retrieval import retrieve
from trustflow.domain.review import answer_state_digest, review_binding_error
from trustflow.ports.interfaces import (
    AnswerGenerator,
    QuestionnaireExporter,
    QuestionnaireParser,
    Store,
)

_RESOLVABLE_WITH_REVIEW = {
    AnswerStatus.REVIEW_REQUIRED,
    AnswerStatus.CONFLICT,
    AnswerStatus.STALE,
}


class TrustFlowService:
    def __init__(
        self,
        *,
        store: Store,
        parser: QuestionnaireParser,
        exporter: QuestionnaireExporter,
        generator: AnswerGenerator,
        policy: PolicySettings | None = None,
    ) -> None:
        self.store = store
        self.parser = parser
        self.exporter = exporter
        self.generator = generator
        self.policy = policy or PolicySettings()

    def _audit(self, event_type: str, entity_id: str, payload: dict[str, object]) -> None:
        self.store.append_audit_event(event_type, entity_id, payload)

    def ingest_source(self, source: SourceDocument) -> None:
        previous = self.store.get_source(source.id)
        impact_count = 0
        if previous is not None:
            proposed_sources = {item.id: item for item in self.store.list_sources()}
            proposed_sources[source.id] = source
            impact_count = len(self._impact_findings(proposed_sources, source.id))
        payload: dict[str, object] = {
            "version": source.version,
            "approved": source.approved,
            "owner": source.owner,
            "replaced": previous is not None,
            "impact_count": impact_count,
        }
        with self.store.transaction() as transaction:
            transaction.put_source(source)
            transaction.append_audit_event("source.ingested", source.id, payload)

    def import_questionnaire(self, path: str | Path) -> Questionnaire:
        questionnaire = self.parser.parse(Path(path))
        with self.store.transaction() as transaction:
            transaction.put_questionnaire(questionnaire)
            transaction.append_audit_event(
                "questionnaire.imported",
                questionnaire.id,
                {"format": questionnaire.format.value, "questions": len(questionnaire.questions)},
            )
        return questionnaire

    def draft(self, questionnaire_id: str) -> list[DraftAnswer]:
        questionnaire = self.store.get_questionnaire(questionnaire_id)
        if questionnaire is None:
            raise NotFoundError(f"questionnaire not found: {questionnaire_id}")
        if self.store.list_answers(questionnaire_id):
            raise InvalidTransitionError("questionnaire has already been drafted")
        sources = self.store.list_sources()
        answers: list[DraftAnswer] = []
        for question in questionnaire.questions:
            evidence = retrieve(question.text, sources, self.policy)
            text, confidence = self.generator.generate(
                question=question.text,
                evidence=evidence,
            )
            status, reasons = decide_status(
                confidence=confidence,
                evidence=evidence,
                sensitivity=question.sensitivity,
                policy=self.policy,
            )
            answers.append(
                DraftAnswer(
                    questionnaire_id=questionnaire.id,
                    question_id=question.id,
                    text=text,
                    status=status,
                    confidence=confidence,
                    evidence=evidence,
                    reasons=reasons,
                )
            )
        with self.store.transaction() as transaction:
            for answer in answers:
                transaction.put_answer(answer)
                transaction.append_audit_event(
                    "answer.drafted",
                    answer.id,
                    {
                        "question_id": answer.question_id,
                        "status": answer.status.value,
                        "source_ids": [item.source_id for item in answer.evidence],
                    },
                )
        return answers

    def review(
        self,
        answer_id: str,
        *,
        reviewer: str,
        state: ReviewState,
        final_text: str = "",
        note: str = "",
    ) -> ReviewDecision:
        answer = self.store.get_answer(answer_id)
        if answer is None:
            raise NotFoundError(f"answer not found: {answer_id}")
        if not reviewer.strip():
            raise InvalidTransitionError("reviewer cannot be blank")
        if answer.status is AnswerStatus.UNANSWERABLE and state in {
            ReviewState.APPROVED,
            ReviewState.EDITED,
        }:
            raise InvalidTransitionError(
                "unanswerable answer has no approved evidence and cannot become an external claim"
            )
        if state in {ReviewState.APPROVED, ReviewState.EDITED} and not final_text.strip():
            raise InvalidTransitionError("approved or edited review requires non-blank final text")
        if state is ReviewState.APPROVED and final_text != answer.text:
            raise InvalidTransitionError("approved review must preserve the exact draft text")
        if state is ReviewState.EDITED and final_text == answer.text:
            raise InvalidTransitionError("edited review must contain a changed final text")
        review = ReviewDecision(
            answer_id=answer.id,
            answer_digest=answer_state_digest(answer),
            reviewer=reviewer,
            state=state,
            final_text="" if state is ReviewState.REJECTED else final_text,
            note=note,
        )
        binding_error = review_binding_error(answer, review)
        if binding_error is not None:
            raise InvalidTransitionError(f"invalid review binding: {binding_error}")
        payload: dict[str, object] = {
            "answer_id": answer.id,
            "answer_digest": review.answer_digest,
            "state": state.value,
            "reviewer": review.reviewer,
        }
        with self.store.transaction() as transaction:
            transaction.put_review(review)
            transaction.append_audit_event("answer.reviewed", review.id, payload)
        return review

    def review_history(self, answer_id: str) -> list[ReviewDecision]:
        if self.store.get_answer(answer_id) is None:
            raise NotFoundError(f"answer not found: {answer_id}")
        return self.store.list_reviews_for_answer(answer_id)

    def _validated_answers(self, questionnaire: Questionnaire) -> list[DraftAnswer]:
        answers = self.store.list_answers(questionnaire.id)
        expected = {question.id for question in questionnaire.questions}
        actual: dict[str, DraftAnswer] = {}
        for answer in answers:
            if answer.question_id in actual:
                raise InvalidTransitionError(f"duplicate drafts for question: {answer.question_id}")
            actual[answer.question_id] = answer
        if set(actual) != expected:
            raise InvalidTransitionError("every question must have exactly one draft before export")
        return [actual[question.id] for question in questionnaire.questions]

    def _validated_reviews(
        self,
        answers: list[DraftAnswer],
    ) -> dict[str, ReviewDecision]:
        reviews: dict[str, ReviewDecision] = {}
        blocked: list[str] = []
        for answer in answers:
            review = self.store.get_review_for_answer(answer.id)
            if review is not None:
                reviews[answer.id] = review
                binding_error = review_binding_error(answer, review)
                if binding_error is not None:
                    blocked.append(f"{answer.question_id}:{binding_error}")
                    continue
            if review is not None and review.state is ReviewState.REJECTED:
                blocked.append(f"{answer.question_id}:rejected")
                continue
            if answer.status is AnswerStatus.ANSWERED:
                continue
            if review is None:
                blocked.append(f"{answer.question_id}:missing_review")
                continue
            if answer.status is AnswerStatus.UNANSWERABLE:
                blocked.append(f"{answer.question_id}:no_evidence")
                continue
            if answer.status in _RESOLVABLE_WITH_REVIEW and review.state not in {
                ReviewState.APPROVED,
                ReviewState.EDITED,
            }:
                blocked.append(f"{answer.question_id}:unresolved")
        if blocked:
            raise InvalidTransitionError(
                "export blocked by unresolved answers: " + ", ".join(blocked)
            )
        return reviews

    def _validate_current_evidence(self, answers: list[DraftAnswer]) -> None:
        current = {source.id: source for source in self.store.list_sources()}
        current_time = datetime.now(UTC)
        blocked: list[str] = []
        for answer in answers:
            if not answer.evidence:
                blocked.append(f"{answer.question_id}:no_evidence")
                continue
            for evidence in answer.evidence:
                source = current.get(evidence.source_id)
                reason: str | None
                if source is None:
                    reason = "source_removed"
                else:
                    reason = evidence_invalidation_reason(
                        source,
                        evidence,
                        self.policy,
                        now=current_time,
                    )
                if reason is not None:
                    blocked.append(f"{answer.question_id}:{evidence.source_id}:{reason}")
        if blocked:
            raise InvalidTransitionError(
                "export blocked by invalid evidence: " + ", ".join(blocked)
            )

    def export(self, questionnaire_id: str, output: str | Path) -> ExportResult:
        questionnaire = self.store.get_questionnaire(questionnaire_id)
        if questionnaire is None:
            raise NotFoundError(f"questionnaire not found: {questionnaire_id}")
        answers = self._validated_answers(questionnaire)
        reviews = self._validated_reviews(answers)
        self._validate_current_evidence(answers)
        result = self.exporter.export(questionnaire, answers, reviews, Path(output))
        self._audit(
            "questionnaire.exported",
            questionnaire.id,
            {"output": str(result.output_path), "answered": result.answered},
        )
        return result

    def _impact_findings(
        self,
        current: dict[str, SourceDocument],
        source_id: str | None = None,
    ) -> list[ImpactFinding]:
        findings: list[ImpactFinding] = []
        current_time = datetime.now(UTC)
        for answer in self.store.list_answers():
            review = self.store.get_review_for_answer(answer.id)
            for evidence in answer.evidence:
                if source_id is not None and evidence.source_id != source_id:
                    continue
                source = current.get(evidence.source_id)
                reason: str | None
                if source is None:
                    reason = "source_removed"
                    current_version = None
                else:
                    reason = evidence_invalidation_reason(
                        source,
                        evidence,
                        self.policy,
                        now=current_time,
                    )
                    current_version = source.version
                if reason is not None:
                    findings.append(
                        ImpactFinding(
                            questionnaire_id=answer.questionnaire_id,
                            answer_id=answer.id,
                            question_id=answer.question_id,
                            source_id=evidence.source_id,
                            previous_version=evidence.source_version,
                            current_version=current_version,
                            reason=reason,
                            review_id=review.id if review is not None else None,
                            review_state=review.state if review is not None else None,
                        )
                    )
        return sorted(
            findings,
            key=lambda item: (
                item.questionnaire_id,
                item.question_id,
                item.answer_id,
                item.source_id,
                item.reason,
            ),
        )

    def impact_scan(self, source_id: str | None = None) -> list[ImpactFinding]:
        current = {source.id: source for source in self.store.list_sources()}
        return self._impact_findings(current, source_id)

    def metrics(self, questionnaire_id: str) -> dict[str, float | int]:
        if self.store.get_questionnaire(questionnaire_id) is None:
            raise NotFoundError(f"questionnaire not found: {questionnaire_id}")
        answers = self.store.list_answers(questionnaire_id)
        total = len(answers)
        return {
            "answers": total,
            "auto_answer_rate": (
                sum(item.status is AnswerStatus.ANSWERED for item in answers) / total
                if total
                else 0.0
            ),
            "review_rate": (
                sum(
                    item.status in {AnswerStatus.REVIEW_REQUIRED, AnswerStatus.CONFLICT}
                    for item in answers
                )
                / total
                if total
                else 0.0
            ),
            "evidence_coverage": (
                sum(bool(item.evidence) for item in answers) / total if total else 0.0
            ),
            "unanswerable_rate": (
                sum(
                    item.status in {AnswerStatus.UNANSWERABLE, AnswerStatus.STALE}
                    for item in answers
                )
                / total
                if total
                else 0.0
            ),
        }

    def evaluate_cases(self, cases: list[EvaluationCase]) -> EvaluationSummary:
        status_hits = 0
        citation_hits = 0
        citation_total = 0
        unsupported = 0
        sensitive_auto = 0
        for case in cases:
            evidence = retrieve(case.question.text, self.store.list_sources(), self.policy)
            text, confidence = self.generator.generate(
                question=case.question.text,
                evidence=evidence,
            )
            status, _ = decide_status(
                confidence=confidence,
                evidence=evidence,
                sensitivity=case.question.sensitivity,
                policy=self.policy,
            )
            status_hits += status is case.expected_status
            actual = {item.source_id for item in evidence}
            citation_hits += len(actual & case.expected_source_ids)
            citation_total += len(case.expected_source_ids)
            unsupported += bool(text and not evidence and status is AnswerStatus.ANSWERED)
            sensitive_auto += (
                case.question.sensitivity.value != "standard" and status is AnswerStatus.ANSWERED
            )
        total = len(cases)
        return EvaluationSummary(
            cases=total,
            status_accuracy=status_hits / total if total else 0.0,
            citation_recall=citation_hits / citation_total if citation_total else 1.0,
            unsupported_answer_rate=unsupported / total if total else 0.0,
            sensitive_auto_approval_rate=sensitive_auto / total if total else 0.0,
        )

    def verify_audit(self) -> None:
        verify_chain(self.store.list_audit())
