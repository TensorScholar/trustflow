from __future__ import annotations

from pathlib import Path

from trustflow.domain.audit import make_event, verify_chain
from trustflow.domain.errors import InvalidTransitionError, NotFoundError
from trustflow.domain.models import (
    AnswerStatus,
    DraftAnswer,
    EvaluationCase,
    EvaluationSummary,
    ImpactFinding,
    PolicySettings,
    Questionnaire,
    ReviewDecision,
    ReviewState,
    SourceDocument,
)
from trustflow.domain.policy import decide_status
from trustflow.domain.retrieval import retrieve
from trustflow.ports.interfaces import (
    AnswerGenerator,
    QuestionnaireExporter,
    QuestionnaireParser,
    Store,
)


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
        events = self.store.list_audit()
        previous = events[-1].event_hash if events else "0" * 64
        self.store.append_audit(
            make_event(
                sequence=len(events) + 1,
                event_type=event_type,
                entity_id=entity_id,
                payload=payload,
                previous_hash=previous,
            )
        )

    def ingest_source(self, source: SourceDocument) -> None:
        self.store.put_source(source)
        self._audit(
            "source.ingested",
            source.id,
            {"version": source.version, "approved": source.approved, "owner": source.owner},
        )

    def import_questionnaire(self, path: str | Path) -> Questionnaire:
        questionnaire = self.parser.parse(Path(path))
        self.store.put_questionnaire(questionnaire)
        self._audit(
            "questionnaire.imported",
            questionnaire.id,
            {"format": questionnaire.format.value, "questions": len(questionnaire.questions)},
        )
        return questionnaire

    def draft(self, questionnaire_id: str) -> list[DraftAnswer]:
        questionnaire = self.store.get_questionnaire(questionnaire_id)
        if questionnaire is None:
            raise NotFoundError(f"questionnaire not found: {questionnaire_id}")
        answers: list[DraftAnswer] = []
        for question in questionnaire.questions:
            evidence = retrieve(question.text, self.store.list_sources(), self.policy)
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
            answer = DraftAnswer(
                questionnaire_id=questionnaire.id,
                question_id=question.id,
                text=text,
                status=status,
                confidence=confidence,
                evidence=evidence,
                reasons=reasons,
            )
            self.store.put_answer(answer)
            answers.append(answer)
            self._audit(
                "answer.drafted",
                answer.id,
                {
                    "question_id": question.id,
                    "status": status.value,
                    "source_ids": [item.source_id for item in evidence],
                },
            )
        return answers

    def review(
        self,
        answer_id: str,
        *,
        reviewer: str,
        state: ReviewState,
        final_text: str,
        note: str = "",
    ) -> ReviewDecision:
        answer = self.store.get_answer(answer_id)
        if answer is None:
            raise NotFoundError(f"answer not found: {answer_id}")
        if state is ReviewState.APPROVED and answer.status is AnswerStatus.UNANSWERABLE:
            raise InvalidTransitionError("unanswerable answer requires edited text")
        if not final_text.strip():
            raise InvalidTransitionError("final answer cannot be blank")
        review = ReviewDecision(
            answer_id=answer.id,
            reviewer=reviewer,
            state=state,
            final_text=final_text,
            note=note,
        )
        self.store.put_review(review)
        self._audit(
            "answer.reviewed",
            review.id,
            {"answer_id": answer.id, "state": state.value, "reviewer": reviewer},
        )
        return review

    def export(self, questionnaire_id: str, output: str | Path):
        questionnaire = self.store.get_questionnaire(questionnaire_id)
        if questionnaire is None:
            raise NotFoundError(f"questionnaire not found: {questionnaire_id}")
        answers = self.store.list_answers(questionnaire_id)
        if len(answers) != len(questionnaire.questions):
            raise InvalidTransitionError("all questions must be drafted before export")
        reviews = {
            answer.id: review
            for answer in answers
            if (review := self.store.get_review_for_answer(answer.id)) is not None
        }
        result = self.exporter.export(questionnaire, answers, reviews, Path(output))
        self._audit(
            "questionnaire.exported",
            questionnaire.id,
            {"output": str(output), "answered": result.answered},
        )
        return result

    def impact_scan(self) -> list[ImpactFinding]:
        findings: list[ImpactFinding] = []
        current = {source.id: source for source in self.store.list_sources()}
        for answer in self.store.list_answers():
            for evidence in answer.evidence:
                source = current.get(evidence.source_id)
                if source is None:
                    findings.append(
                        ImpactFinding(
                            answer_id=answer.id,
                            question_id=answer.question_id,
                            source_id=evidence.source_id,
                            previous_version=evidence.source_version,
                            current_version=None,
                            reason="source_removed",
                        )
                    )
                elif source.version != evidence.source_version:
                    findings.append(
                        ImpactFinding(
                            answer_id=answer.id,
                            question_id=answer.question_id,
                            source_id=evidence.source_id,
                            previous_version=evidence.source_version,
                            current_version=source.version,
                            reason="source_version_changed",
                        )
                    )
        return findings

    def metrics(self, questionnaire_id: str) -> dict[str, float | int]:
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
                    item.status
                    in {AnswerStatus.REVIEW_REQUIRED, AnswerStatus.CONFLICT}
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
                case.question.sensitivity.value != "standard"
                and status is AnswerStatus.ANSWERED
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
