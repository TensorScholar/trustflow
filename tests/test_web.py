import io
import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from trustflow.web.app import create_app


def test_health(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "web.db", tmp_path / "uploads"))
    assert client.get("/health").json() == {"status": "ok"}


def test_questionnaire_import_uses_upload_not_server_path(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "web.db", tmp_path / "uploads"))
    response = client.post(
        "/questionnaires/import",
        files={
            "file": (
                "questions.json",
                io.BytesIO(json.dumps({"questions": ["Question?"]}).encode()),
                "application/json",
            )
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["questions"][0]["text"] == "Question?"
    assert "source_path" not in payload
    assert len(list((tmp_path / "uploads").iterdir())) == 1

    path_payload = client.post(
        "/questionnaires/import",
        json={"path": "/etc/passwd"},
    )
    assert path_payload.status_code == 422


def test_review_uses_json_body(tmp_path) -> None:
    client = TestClient(create_app(tmp_path / "web.db", tmp_path / "uploads"))
    source = {
        "id": "source",
        "title": "Policy",
        "owner": "security",
        "version": "1",
        "content": "Question evidence.",
        "source_uri": "policy://source",
    }
    assert client.post("/sources", json=source).status_code == 200
