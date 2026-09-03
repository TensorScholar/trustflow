import io
import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from trustflow.web.app import create_app


def _client(tmp_path, *, host: str = "127.0.0.1", allow_remote: bool = False) -> TestClient:
    return TestClient(
        create_app(
            tmp_path / "web.db",
            tmp_path / "uploads",
            allow_remote=allow_remote,
        ),
        client=(host, 50000),
    )


def test_health(tmp_path) -> None:
    client = _client(tmp_path)
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_remote_client_is_rejected_by_default(tmp_path) -> None:
    client = _client(tmp_path, host="198.51.100.10")
    response = client.get("/health")
    assert response.status_code == 403
    assert response.json() == {"detail": "remote API access is disabled"}
    assert response.headers["cache-control"] == "no-store"


def test_remote_client_requires_explicit_unsafe_opt_in(tmp_path) -> None:
    client = _client(tmp_path, host="198.51.100.10", allow_remote=True)
    assert client.get("/health").status_code == 200


def test_questionnaire_import_uses_upload_not_server_path(tmp_path) -> None:
    client = _client(tmp_path)
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
    client = _client(tmp_path)
    source = {
        "id": "source",
        "title": "Policy",
        "owner": "security",
        "version": "1",
        "content": "Question evidence.",
        "source_uri": "policy://source",
    }
    assert client.post("/sources", json=source).status_code == 200
