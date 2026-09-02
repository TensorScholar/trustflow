"""Strict domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Confidence = Annotated[float, Field(ge=0, le=1)]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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
    id: NonEmptyText
    title: NonEmptyText
    owner: NonEmptyText
    version: NonEmptyText
    content: str = Field(min_length=1, max_length=5_000_000)
    source_uri: NonEmptyText
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
    id: NonEmptyText
    text: str = Field(min_length=2, max_length=20_000)
    location: QuestionLocation
    sensitivity: QuestionSensitivity = QuestionSensitivity.STANDARD
    required: bool = True


class Questionnaire(StrictModel):
    id: str = Field(default_factory=lambda: f"qnr_{uuid4().hex}")
    title: NonEmptyText
    source_path: NonEmptyText
    source_digest: str = Field(default="0" * 64, pattern=r"^[0-9a-f]{64}$")
    format: DocumentFormat
    questions: tuple[Question, ...]
    imported_at: AwareDatetime = Field(default_factory=utc_now)


class Evidence(StrictModel):
    source_id: NonEmptyText
    source_title: NonEmptyText
    source_uri: NonEmptyText
    source_version: NonEmptyText
    source_digest: str = Field(default="0" * 64, pattern=r"^[0-9a-f]{64}$")
    source_provenance_digest: str = Field(default="0" * 64, pattern=r"^[0-9a-f]{64}$")
    owner: NonEmptyText
    excerpt: str
    score: Confidence
    updated_at: AwareDatetime
    valid_until: AwareDatetime | None = None


class DraftAnswer(StrictModel):
    id: str = Field(default_factory=lambda: f"ans_{uuid4().hex}")
    questionnaire_id: NonEmptyText
    question_id: NonEmptyText
    text: str
    status: AnswerStatus
    confidence: Confidence
    evidence: tuple[Evidence, ...] = ()
    reasons: tuple[str, ...] = ()
    generated_at: AwareDatetime = Field(default_factory=utc_now)


class ReviewDecision(StrictModel):
    id: str = Field(default_factory=lambda: f"rev_{uuid4().hex}")
    answer_id: NonEmptyText
    answer_digest: str = Field(default="0" * 64, pattern=r"^[0-9a-f]{64}$")
    reviewer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=320)]
    state: ReviewState
    final_text: str = Field(default="", max_length=100_000)
    note: str = Field(default="", max_length=20_000)
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_final_text(self) -> Self:
        if self.state in {ReviewState.APPROVED, ReviewState.EDITED} and not self.final_text.strip():
            raise ValueError("approved or edited review requires non-blank final_text")
        if self.state is ReviewState.REJECTED and self.final_text:
            raise ValueError("rejected review cannot carry final_text")
        return self


class ExportResult(StrictModel):
    questionnaire_id: str
    output_path: str
    format: DocumentFormat
    answered: int
    review_required: int
    unanswerable: int
    exported_at: AwareDatetime = Field(default_factory=utc_now)


class ImpactFinding(StrictModel):
    questionnaire_id: str
    answer_id: str
    question_id: str
    source_id: str
    previous_version: str
    current_version: str | None
    reason: str
    review_id: str | None = None
    review_state: ReviewState | None = None


class PolicySettings(StrictModel):
    minimum_evidence_score: Confidence = 0.28
    minimum_answer_confidence: Confidence = 0.62
    maximum_source_age_days: int = Field(default=365, ge=1)
    sensitive_requires_review: bool = True
    require_approved_sources: bool = True
    maximum_file_bytes: int = Field(default=20_000_000, ge=1)
    maximum_archive_members: int = Field(default=5000, ge=1)
    maximum_member_bytes: int = Field(default=25_000_000, ge=1)
    maximum_uncompressed_bytes: int = Field(default=100_000_000, ge=1)
    maximum_compression_ratio: float = Field(default=100.0, ge=1.0)
    maximum_pdf_pages: int = Field(default=500, ge=1)
    maximum_questions: int = Field(default=10_000, ge=1)


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
