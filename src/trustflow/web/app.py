from __future__ import annotations

from pathlib import Path

from trustflow.application.bootstrap import build_service
from trustflow.domain.models import ReviewState, SourceDocument


def create_app(database: str | Path = "trustflow.db") -> object:
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:
        raise RuntimeError("Install TrustFlow with the 'web' extra.") from exc

    service = build_service(database)
    app = FastAPI(title="TrustFlow", version="0.1.0rc1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/sources")
    def source(item: SourceDocument) -> dict[str, object]:
        service.ingest_source(item)
        return item.model_dump(mode="json")

    @app.post("/questionnaires/import")
    def import_questionnaire(path: str) -> dict[str, object]:
        try:
            return service.import_questionnaire(path).model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/questionnaires/{identifier}/draft")
    def draft(identifier: str) -> list[dict[str, object]]:
        try:
            return [item.model_dump(mode="json") for item in service.draft(identifier)]
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/answers/{identifier}/review")
    def review(
        identifier: str,
        reviewer: str,
        final_text: str,
        state: ReviewState = ReviewState.APPROVED,
    ) -> dict[str, object]:
        try:
            return service.review(
                identifier,
                reviewer=reviewer,
                state=state,
                final_text=final_text,
            ).model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/questionnaires/{identifier}/metrics")
    def metrics(identifier: str) -> dict[str, object]:
        return service.metrics(identifier)

    return app
