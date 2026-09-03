import io
import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from trustflow.web.app import create_app


def _client(tmp_path) -> TestClient:
    return TestClient(
        create_app(tmp_path / "web.db", tmp_path / "uploads"),
        client=("127.0.0.1", 50000),
    )


def _source(version: str, color: str) -> dict[str, object]:
    return {
        "id": "company",
        "title": "Company profile",
        "owner": "trust",
        "version": version,
        "content": f"Our favorite color is {color}.",
        "source_uri": "policy://company/profile",
        "tags": ["favorite", "color", color],
    }


def test_api_exposes_revalidation_and_governance_metrics(tmp_path) -> None:
    client = _client(tmp_path)
    assert client.post("/sources", json=_source("1", "blue")).status_code == 200
    imported = client.post(
        "/questionnaires/import",
        files={
            "file": (
                "questions.json",
                io.BytesIO(json.dumps({"questions": ["What is your favorite color?"]}).encode()),
                "application/json",
            )
        },
    )
    assert imported.status_code == 200
    questionnaire_id = imported.json()["id"]

    drafted = client.post(f"/questionnaires/{questionnaire_id}/draft")
    assert drafted.status_code == 200
    assert drafted.json()[0]["status"] == "answered"

    assert client.post("/sources", json=_source("2", "green")).status_code == 200
    drifted = client.get(f"/questionnaires/{questionnaire_id}/governance-metrics")
    assert drifted.status_code == 200
    assert drifted.json()["revalidation_required_answers"] == 1
    assert drifted.json()["external_claim_ready_rate"] == 0.0

    revalidated = client.post(f"/questionnaires/{questionnaire_id}/revalidate")
    assert revalidated.status_code == 200
    payload = revalidated.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "review_required"
    assert "source_change_revalidation" in payload[0]["reasons"]

    pending = client.get(f"/questionnaires/{questionnaire_id}/governance-metrics")
    assert pending.status_code == 200
    assert pending.json()["revalidation_required_answers"] == 0
    assert pending.json()["review_completion_rate"] == 0.0


def test_metrics_endpoints_fail_closed_for_unknown_questionnaire(tmp_path) -> None:
    client = _client(tmp_path)
    assert client.get("/questionnaires/missing/metrics").status_code == 400
    assert client.get("/questionnaires/missing/governance-metrics").status_code == 400
    assert client.post("/questionnaires/missing/revalidate").status_code == 400
