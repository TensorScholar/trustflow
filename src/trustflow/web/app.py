import logging
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from trustflow._version import __version__
from trustflow.application.bootstrap import build_service
from trustflow.domain.errors import TrustFlowError, UnsafeDocumentError
from trustflow.domain.models import Questionnaire, ReviewState, SourceDocument

logger = logging.getLogger(__name__)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(min_length=1, max_length=320)
    state: ReviewState = ReviewState.APPROVED
    final_text: str = Field(default="", max_length=100_000)
    note: str = Field(default="", max_length=20_000)


def _public_questionnaire(item: Questionnaire) -> dict[str, object]:
    payload = item.model_dump(mode="json")
    payload.pop("source_path", None)
    return payload


def create_app(
    database: str | Path = "trustflow.db",
    upload_dir: str | Path = ".trustflow/uploads",
) -> FastAPI:
    service = build_service(database)
    upload_root = Path(upload_dir).expanduser().resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="TrustFlow", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/sources")
    def source(item: SourceDocument) -> dict[str, object]:
        try:
            service.ingest_source(item)
            return item.model_dump(mode="json")
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/questionnaires/import")
    async def import_questionnaire(
        file: Annotated[UploadFile, File(description="Questionnaire file")],
    ) -> dict[str, object]:
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

    @app.post("/questionnaires/{identifier}/draft")
    def draft(identifier: str) -> list[dict[str, object]]:
        try:
            return [item.model_dump(mode="json") for item in service.draft(identifier)]
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/answers/{identifier}/review")
    def review(identifier: str, request: ReviewRequest) -> dict[str, object]:
        try:
            return service.review(
                identifier,
                reviewer=request.reviewer,
                state=request.state,
                final_text=request.final_text,
                note=request.note,
            ).model_dump(mode="json")
        except TrustFlowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/questionnaires/{identifier}/metrics")
    def metrics(identifier: str) -> dict[str, float | int]:
        return service.metrics(identifier)

    return app
