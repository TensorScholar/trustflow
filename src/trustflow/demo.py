from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from trustflow.application.bootstrap import build_service
from trustflow.domain.models import AnswerStatus, ReviewState, SourceDocument


def run_demo(directory: str | Path | None = None) -> dict[str, object]:
    root = Path(directory) if directory else Path(tempfile.mkdtemp(prefix="trustflow-demo-"))
    root.mkdir(parents=True, exist_ok=True)
    questionnaire_path = root / "questionnaire.json"
    questionnaire_path.write_text(
        json.dumps(
            {
                "questions": [
                    "Do you encrypt customer data at rest?",
                    "Do you provide legal indemnity?",
                    "What is your favorite color?",
                ]
            }
        ),
        encoding="utf-8",
    )
    service = build_service(root / "trustflow.db")
    service.ingest_source(
        SourceDocument(
            id="src_security",
            title="Encryption standard",
            owner="security",
            version="2026.1",
            content=(
                "Customer data is encrypted at rest using AES-256 and in transit using TLS 1.3."
            ),
            source_uri="policy://security/encryption",
            updated_at=datetime.now(UTC),
            tags=frozenset({"encryption", "customer", "data", "rest"}),
        )
    )
    service.ingest_source(
        SourceDocument(
            id="src_legal",
            title="Contracting policy",
            owner="legal",
            version="2026.2",
            content=(
                "Indemnity terms are negotiated in the governing agreement "
                "and require legal review."
            ),
            source_uri="policy://legal/contracting",
            updated_at=datetime.now(UTC),
            tags=frozenset({"legal", "indemnity", "contract"}),
        )
    )
    questionnaire = service.import_questionnaire(questionnaire_path)
    answers = service.draft(questionnaire.id)
    for answer in answers:
        if answer.status is AnswerStatus.ANSWERED:
            continue
        if answer.status is AnswerStatus.UNANSWERABLE:
            final_text = "Not applicable to this demonstration."
        else:
            final_text = answer.text
        service.review(
            answer.id,
            reviewer="demo-reviewer",
            state=ReviewState.EDITED,
            final_text=final_text,
            note="Deterministic demonstration review.",
        )
    output = root / "completed.json"
    result = service.export(questionnaire.id, output)
    service.verify_audit()
    return {
        "questionnaire": questionnaire.model_dump(mode="json"),
        "answers": [item.model_dump(mode="json") for item in answers],
        "metrics": service.metrics(questionnaire.id),
        "export": result.model_dump(mode="json"),
        "output": str(output),
        "audit_events": len(service.store.list_audit()),
    }
