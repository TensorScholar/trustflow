"""Strict domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Confidence = Annotated[float, Field(ge=0, le=1)]


def utc_now() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class DocumentFormat(StrEnum):
    XLSX = "xlsx"
    DOCX = "docx"
    CSV = "csv"
    JSON = "json"
    MARKDOWN = "md"
    PDF = "pdf"


class SourceClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


class QuestionSensitivity(StrEnum):
    STANDARD = "standard"
    SECURITY = "security"
    LEGAL = "legal"
    PRIVACY = "privacy"
    FINANCIAL = "financial"


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    REVIEW_REQUIRED = "review_required"
    UNANSWERABLE = "unanswerable"
    STALE = "stale"
    CONFLICT = "conflict"


class ReviewState(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class SourceDocument(StrictModel):
    id: str
    title: str
    owner: str
    version: str
    content: str = Field(min_length=1)
    source_uri: str
    classification: SourceClassification = SourceClassification.INTERNAL
    approved: bool = True
    updated_at: AwareDatetime = Field(default_factory=utc_now)
    valid_until: AwareDatetime | None = None
    tags: frozenset[str] = frozenset()


class QuestionLocation(StrictModel):
    format: DocumentFormat
    sheet: str | None = None
    cell: str | None = None
    paragraph: int | None = None
    row: int | None = None
    key: str | None = None


class Question(StrictModel):
    id: str
    text: str = Field(min_length=2, max_length=20_000)
    location: QuestionLocation
    sensitivity: QuestionSensitivity = QuestionSensitivity.STANDARD
    required: bool = True


class Questionnaire(StrictModel):
    id: str = Field(default_factory=lambda: f"qnr_{uuid4().hex}")
    title: str
    source_path: str
    format: DocumentFormat
    questions: tuple[Question, ...]
    imported_at: AwareDatetime = Field(default_factory=utc_now)


class Evidence(StrictModel):
    source_id: str
    source_title: str
    source_uri: str
    source_version: str
    owner: str
    excerpt: str
    score: Confidence
    updated_at: AwareDatetime
    valid_until: AwareDatetime | None = None


class DraftAnswer(StrictModel):
    id: str = Field(default_factory=lambda: f"ans_{uuid4().hex}")
    questionnaire_id: str
    question_id: str
    text: str
    status: AnswerStatus
    confidence: Confidence
    evidence: tuple[Evidence, ...] = ()
    reasons: tuple[str, ...] = ()
    generated_at: AwareDatetime = Field(default_factory=utc_now)


class ReviewDecision(StrictModel):
    id: str = Field(default_factory=lambda: f"rev_{uuid4().hex}")
    answer_id: str
    reviewer: str
    state: ReviewState
    final_text: str
    note: str = ""
    created_at: AwareDatetime = Field(default_factory=utc_now)


class ExportResult(StrictModel):
    questionnaire_id: str
    output_path: str
    format: DocumentFormat
    answered: int
    review_required: int
    unanswerable: int
    exported_at: AwareDatetime = Field(default_factory=utc_now)


class ImpactFinding(StrictModel):
    answer_id: str
    question_id: str
    source_id: str
    previous_version: str
    current_version: str | None
    reason: str


class PolicySettings(StrictModel):
    minimum_evidence_score: Confidence = 0.28
    minimum_answer_confidence: Confidence = 0.62
    maximum_source_age_days: int = Field(default=365, ge=1)
    sensitive_requires_review: bool = True
    require_approved_sources: bool = True
    maximum_file_bytes: int = Field(default=20_000_000, ge=1)
    maximum_archive_members: int = Field(default=5000, ge=1)
    maximum_uncompressed_bytes: int = Field(default=100_000_000, ge=1)


class AuditEvent(StrictModel):
    sequence: int
    event_type: str
    entity_id: str
    payload: dict[str, object]
    occurred_at: AwareDatetime = Field(default_factory=utc_now)
    previous_hash: str
    event_hash: str


class EvaluationCase(StrictModel):
    id: str
    question: Question
    expected_status: AnswerStatus
    expected_source_ids: frozenset[str] = frozenset()


class EvaluationSummary(StrictModel):
    cases: int
    status_accuracy: float
    citation_recall: float
    unsupported_answer_rate: float
    sensitive_auto_approval_rate: float
