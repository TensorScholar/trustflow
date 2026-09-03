import logging
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from trustflow._version import __version__
from trustflow.application.bootstrap import build_service
from trustflow.domain.errors import TrustFlowError, UnsafeDocumentError
from trustflow.domain.models import (
    DocumentFormat,
    DraftAnswer,
    Question,
    Questionnaire,
    ReviewDecision,
    ReviewState,
    SourceDocument,
)

logger = logging.getLogger(__name__)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1, max_length=320)
    state: ReviewState = ReviewState.APPROVED
    final_text: str = Field(default="", max_length=100_000)
    note: str = Field(default="", max_length=20_000)


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"


class QuestionnaireResponse(BaseModel):
    """Public questionnaire representation that never exposes the server-side source path."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    source_digest: str
    format: DocumentFormat
    questions: tuple[Question, ...]
    imported_at: AwareDatetime


class MetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: int
    auto_answer_rate: float
    review_rate: float
    evidence_coverage: float
    unanswerable_rate: float


class GovernanceMetricsResponse(MetricsResponse):
    current_evidence_rate: float
    external_claim_ready_rate: float
    external_claim_blocked_rate: float
    review_required_answers: int
    review_completed_answers: int
    review_completion_rate: float
    reviewer_edit_rate: float
    revalidation_required_answers: int
    revalidation_required_rate: float
    impact_findings: int
    time_to_first_draft_seconds: float
    review_turnaround_samples: int
    median_review_turnaround_seconds: float


def _public_questionnaire(item: Questionnaire) -> QuestionnaireResponse:
    payload = item.model_dump(mode="json")
    payload.pop("source_path", None)
    return QuestionnaireResponse.model_validate(payload)


def _is_loopback_client(host: str | None) -> bool:
    if host is None:
        return False
    candidate = host.strip().removeprefix("[").removesuffix("]")
    if candidate.casefold() == "localhost":
        return True
    try:
        return ip_address(candidate).is_loopback
    except ValueError:
        return False


def _apply_security_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def create_app(
    database: str | Path = "trustflow.db",
    upload_dir: str | Path = ".trustflow/uploads",
    *,
    allow_remote: bool = False,
) -> FastAPI:
    service = build_service(database)
    upload_root = Path(upload_dir).expanduser().resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="TrustFlow", version=__version__)

    @app.middleware("http")
    async def security_boundary(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        client_host = request.client.host if request.client is not None else None
        if not allow_remote and not _is_loopback_client(client_host):
            return _apply_security_headers(
                JSONResponse(status_code=403, content={"detail": "remote API access is disabled"})
            )
        response = await call_next(request)
        return _apply_security_headers(response)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/sources", response_model=SourceDocument)
    def source(item: SourceDocument) -> SourceDocument:
        try:
            service.ingest_source(item)
            return item
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/questionnaires/import", response_model=QuestionnaireResponse)
    async def import_questionnaire(
        file: Annotated[UploadFile, File(description="Questionnaire file")],
    ) -> QuestionnaireResponse:
        original_name = Path(file.filename or "questionnaire").name
        suffix = Path(original_name).suffix.casefold()
        destination = upload_root / f"{uuid4().hex}{suffix}"
        total = 0
        try:
            with destination.open("xb") as handle:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > service.policy.maximum_file_bytes:
                        raise UnsafeDocumentError("document exceeds configured size limit")
                    handle.write(chunk)
            questionnaire = service.import_questionnaire(destination)
            return _public_questionnaire(questionnaire)
        except TrustFlowError as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            destination.unlink(missing_ok=True)
            logger.exception("unexpected questionnaire import failure")
            raise HTTPException(status_code=500, detail="internal import failure") from exc
        finally:
            await file.close()

    @app.post("/questionnaires/{identifier}/draft", response_model=list[DraftAnswer])
    def draft(identifier: str) -> list[DraftAnswer]:
        try:
            return service.draft(identifier)
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/questionnaires/{identifier}/revalidate", response_model=list[DraftAnswer])
    def revalidate(identifier: str, source_id: str | None = None) -> list[DraftAnswer]:
        try:
            return service.revalidate(identifier, source_id=source_id)
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/answers/{identifier}/review", response_model=ReviewDecision)
    def review(identifier: str, request: ReviewRequest) -> ReviewDecision:
        try:
            return service.review(
                identifier,
                reviewer=request.reviewer,
                state=request.state,
                final_text=request.final_text,
                note=request.note,
            )
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/questionnaires/{identifier}/metrics", response_model=MetricsResponse)
    def metrics(identifier: str) -> MetricsResponse:
        try:
            return MetricsResponse.model_validate(service.metrics(identifier))
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(
        "/questionnaires/{identifier}/governance-metrics",
        response_model=GovernanceMetricsResponse,
    )
    def governance_metrics(identifier: str) -> GovernanceMetricsResponse:
        try:
            return GovernanceMetricsResponse.model_validate(service.governance_metrics(identifier))
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
