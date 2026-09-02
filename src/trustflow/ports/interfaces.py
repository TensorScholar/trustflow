from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from trustflow.domain.models import (
    AuditEvent,
    DraftAnswer,
    ExportRecoveryStatus,
    ExportResult,
    Questionnaire,
    ReviewDecision,
    SourceDocument,
)


@dataclass(frozen=True)
class PreparedExport:
    operation_id: str
    staging_path: Path
    output_path: Path
    artifact_digest: str
    result: ExportResult


class StoreTransaction(Protocol):
    """Atomic persistence boundary for governed state mutations and their audit events."""

    def put_source(self, source: SourceDocument) -> None: ...
    def put_questionnaire(self, questionnaire: Questionnaire) -> None: ...
    def put_answer(self, answer: DraftAnswer) -> None: ...
    def put_review(self, review: ReviewDecision) -> None: ...
    def append_audit_event(
        self,
        event_type: str,
        entity_id: str,
        payload: dict[str, object],
    ) -> AuditEvent: ...
    def has_audit_event(self, event_type: str, entity_id: str) -> bool: ...


class Store(Protocol):
    """Application-facing persistence port; governed writes must use ``transaction()``."""

    def transaction(self) -> AbstractContextManager[StoreTransaction]: ...
    def get_source(self, source_id: str) -> SourceDocument | None: ...
    def list_sources(self) -> list[SourceDocument]: ...
    def get_questionnaire(self, questionnaire_id: str) -> Questionnaire | None: ...
    def get_answer(self, answer_id: str) -> DraftAnswer | None: ...
    def list_answers(self, questionnaire_id: str | None = None) -> list[DraftAnswer]: ...
    def get_review_for_answer(self, answer_id: str) -> ReviewDecision | None: ...
    def list_reviews_for_answer(self, answer_id: str) -> list[ReviewDecision]: ...
    def append_audit_event(
        self,
        event_type: str,
        entity_id: str,
        payload: dict[str, object],
    ) -> AuditEvent: ...
    def list_audit(self) -> list[AuditEvent]: ...


class QuestionnaireParser(Protocol):
    def parse(self, path: Path) -> Questionnaire: ...


class QuestionnaireExporter(Protocol):
    def export(
        self,
        questionnaire: Questionnaire,
        answers: list[DraftAnswer],
        reviews: dict[str, ReviewDecision],
        output: Path,
    ) -> ExportResult: ...

    def prepare(
        self,
        questionnaire: Questionnaire,
        answers: list[DraftAnswer],
        reviews: dict[str, ReviewDecision],
        output: Path,
        operation_id: str,
    ) -> PreparedExport: ...

    def commit_prepared(self, prepared: PreparedExport) -> ExportResult: ...
    def discard_prepared(self, prepared: PreparedExport) -> None: ...
    def inspect_recovery(
        self,
        staging_path: Path,
        output_path: Path,
        expected_digest: str,
    ) -> ExportRecoveryStatus: ...
    def recover_prepared(
        self,
        staging_path: Path,
        output_path: Path,
        expected_digest: str,
    ) -> ExportRecoveryStatus: ...


class AnswerGenerator(Protocol):
    def generate(
        self,
        *,
        question: str,
        evidence: tuple[object, ...],
    ) -> tuple[str, float]: ...
