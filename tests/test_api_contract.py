from pathlib import Path

from trustflow.web.app import create_app


def _response_schema(
    schema: dict[str, object],
    path: str,
    method: str,
) -> dict[str, object]:
    paths = schema["paths"]
    assert isinstance(paths, dict)
    operation = paths[path][method]  # type: ignore[index]
    response = operation["responses"]["200"]  # type: ignore[index]
    return response["content"]["application/json"]["schema"]  # type: ignore[index,return-value]


def test_openapi_uses_explicit_response_contracts(tmp_path: Path) -> None:
    schema = create_app(tmp_path / "contract.db", tmp_path / "uploads").openapi()

    expected_refs = {
        ("/health", "get"): "#/components/schemas/HealthResponse",
        ("/sources", "post"): "#/components/schemas/SourceDocument",
        ("/questionnaires/import", "post"): "#/components/schemas/QuestionnaireResponse",
        ("/answers/{identifier}/review", "post"): "#/components/schemas/ReviewDecision",
        ("/questionnaires/{identifier}/metrics", "get"): "#/components/schemas/MetricsResponse",
        (
            "/questionnaires/{identifier}/governance-metrics",
            "get",
        ): "#/components/schemas/GovernanceMetricsResponse",
    }
    for endpoint, expected_ref in expected_refs.items():
        assert _response_schema(schema, *endpoint) == {"$ref": expected_ref}

    for path in (
        "/questionnaires/{identifier}/draft",
        "/questionnaires/{identifier}/revalidate",
    ):
        response_schema = _response_schema(schema, path, "post")
        assert response_schema["type"] == "array"
        assert response_schema["items"] == {"$ref": "#/components/schemas/DraftAnswer"}

    components = schema["components"]
    assert isinstance(components, dict)
    component_schemas = components["schemas"]
    assert isinstance(component_schemas, dict)
    questionnaire_response = component_schemas["QuestionnaireResponse"]
    assert isinstance(questionnaire_response, dict)
    properties = questionnaire_response["properties"]
    assert isinstance(properties, dict)
    assert "source_path" not in properties
