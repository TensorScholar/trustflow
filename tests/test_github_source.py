import base64
from collections.abc import Callable

import httpx
import pytest

from trustflow.adapters.github_source import GitHubEvidenceSource, GitHubSourceError
from trustflow.domain.models import SourceClassification

COMMIT_SHA = "a" * 40


def _transport(
    content: bytes = b"Customer data is encrypted at rest with AES-256.",
    *,
    content_type: str = "file",
    declared_size: int | None = None,
    encoding: str | None = "base64",
    encoded_content: str | None = None,
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "/commits/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "sha": COMMIT_SHA,
                    "commit": {"committer": {"date": "2026-08-31T10:00:00Z"}},
                },
            )
        payload = {
            "type": content_type,
            "size": len(content) if declared_size is None else declared_size,
            "encoding": encoding,
            "content": (
                base64.b64encode(content).decode("ascii")
                if encoded_content is None
                else encoded_content
            ),
        }
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler), requests


def _load(
    transport: httpx.BaseTransport,
    **overrides: object,
):
    kwargs: dict[str, object] = {
        "repository": "acme/security-policies",
        "path": "docs/security.md",
        "ref": "main",
        "identifier": "github-security",
        "title": "GitHub security policy",
        "evidence_owner": "security",
    }
    kwargs.update(overrides)
    with GitHubEvidenceSource(token="secret-token", transport=transport) as connector:
        return connector.load_file(**kwargs)  # type: ignore[arg-type]


def test_github_source_resolves_ref_then_pins_exact_commit() -> None:
    transport, requests = _transport()
    source = _load(
        transport,
        ref="release/2026",
        path="docs/security policy.md",
    )

    assert source.version == COMMIT_SHA
    assert source.content == "Customer data is encrypted at rest with AES-256."
    assert source.approved is False
    assert source.updated_at.isoformat() == "2026-08-31T10:00:00+00:00"
    assert source.source_uri == (
        f"https://github.com/acme/security-policies/blob/{COMMIT_SHA}/docs/security%20policy.md"
    )
    assert len(requests) == 2
    assert b"release%2F2026" in requests[0].url.raw_path
    assert requests[1].url.params["ref"] == COMMIT_SHA
    assert all(request.headers["authorization"] == "Bearer secret-token" for request in requests)
    assert "secret-token" not in source.model_dump_json()


def test_github_source_requires_explicit_approval() -> None:
    transport, _ = _transport()
    source = _load(
        transport,
        approved=True,
        classification=SourceClassification.CONFIDENTIAL,
    )
    assert source.approved is True
    assert source.classification is SourceClassification.CONFIDENTIAL


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repository", "acme/security/policies"),
        ("repository", "acme/../policies"),
        ("path", "/etc/passwd"),
        ("path", "docs/../secret.md"),
        ("path", "docs\\secret.md"),
        ("path", "docs//secret.md"),
        ("ref", ""),
        ("ref", "main\nAuthorization: bad"),
    ],
)
def test_github_source_rejects_unsafe_locator_before_network(field: str, value: str) -> None:
    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected network request: {request.url}")

    with GitHubEvidenceSource(
        token="secret-token",
        transport=httpx.MockTransport(fail_if_called),
    ) as connector:
        kwargs = {
            "repository": "acme/security-policies",
            "path": "docs/security.md",
            "ref": "main",
            "identifier": "github-security",
            "title": "GitHub security policy",
            "evidence_owner": "security",
        }
        kwargs[field] = value
        with pytest.raises(GitHubSourceError):
            connector.load_file(**kwargs)


def test_github_source_does_not_follow_redirects_or_echo_error_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            302,
            headers={"location": "https://attacker.example/steal"},
            text="secret-token should never be echoed",
        )

    with GitHubEvidenceSource(
        token="secret-token",
        transport=httpx.MockTransport(handler),
    ) as connector:
        with pytest.raises(GitHubSourceError, match="status 302") as exc_info:
            connector.load_file(
                repository="acme/security-policies",
                path="docs/security.md",
                ref="main",
                identifier="github-security",
                title="GitHub security policy",
                evidence_owner="security",
            )
    assert "secret-token" not in str(exc_info.value)


def test_github_source_rejects_non_file_entries() -> None:
    transport, _ = _transport(content_type="dir")
    with pytest.raises(GitHubSourceError, match="regular file"):
        _load(transport)


def test_github_source_rejects_declared_oversize_before_decode() -> None:
    transport, _ = _transport(declared_size=1_000_001)
    with pytest.raises(GitHubSourceError, match="size limit"):
        _load(transport)


@pytest.mark.parametrize(
    ("content", "declared_size", "encoded_content", "match"),
    [
        (b"abc", 3, "%%%", "valid base64"),
        (b"abc", 4, None, "size does not match"),
        (b"\xff\xfe", 2, None, "UTF-8"),
        (b"hello\x00world", 11, None, "binary"),
    ],
)
def test_github_source_rejects_invalid_inline_content(
    content: bytes,
    declared_size: int,
    encoded_content: str | None,
    match: str,
) -> None:
    transport, _ = _transport(
        content,
        declared_size=declared_size,
        encoded_content=encoded_content,
    )
    with pytest.raises(GitHubSourceError, match=match):
        _load(transport)


def test_github_source_rejects_invalid_api_shape() -> None:
    responses: list[Callable[[httpx.Request], httpx.Response]] = [
        lambda request: httpx.Response(200, json={"sha": "not-a-sha", "commit": {}}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses[0](request)

    with GitHubEvidenceSource(
        token="secret-token",
        transport=httpx.MockTransport(handler),
    ) as connector:
        with pytest.raises(GitHubSourceError, match="invalid response shape"):
            connector.load_file(
                repository="acme/security-policies",
                path="docs/security.md",
                ref="main",
                identifier="github-security",
                title="GitHub security policy",
                evidence_owner="security",
            )


def test_github_source_rejects_whitespace_in_token() -> None:
    with pytest.raises(GitHubSourceError, match="token"):
        GitHubEvidenceSource(token=" secret-token ")
