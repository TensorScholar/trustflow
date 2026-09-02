"""Read-only, commit-pinned GitHub evidence ingestion."""

from __future__ import annotations

import base64
import binascii
import re
from datetime import UTC
from typing import TypeVar
from urllib.parse import quote

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from trustflow.domain.errors import TrustFlowError
from trustflow.domain.models import SourceClassification, SourceDocument

_REPOSITORY_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_COMMIT_SHA = r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"
_DEFAULT_MAXIMUM_FILE_BYTES = 1_000_000

TModel = TypeVar("TModel", bound=BaseModel)


class GitHubSourceError(TrustFlowError):
    """A GitHub evidence source could not be retrieved or validated safely."""


class _ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Committer(_ApiModel):
    date: AwareDatetime


class _Commit(_ApiModel):
    committer: _Committer


class _CommitResponse(_ApiModel):
    sha: str = Field(pattern=_COMMIT_SHA)
    commit: _Commit


class _ContentResponse(_ApiModel):
    type: str
    size: int = Field(ge=0)
    encoding: str | None = None
    content: str | None = None


def _repository_parts(repository: str) -> tuple[str, str]:
    parts = repository.split("/")
    if len(parts) != 2 or not all(_REPOSITORY_COMPONENT.fullmatch(part) for part in parts):
        raise GitHubSourceError("repository must be an explicit owner/name pair")
    owner, name = parts
    if owner in {".", ".."} or name in {".", ".."}:
        raise GitHubSourceError("repository contains an unsafe path component")
    return owner, name


def _safe_repository_path(path: str) -> str:
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        raise GitHubSourceError("GitHub source path must be a relative repository file path")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise GitHubSourceError("GitHub source path contains an unsafe path component")
    return "/".join(parts)


def _safe_ref(ref: str) -> str:
    if not ref or len(ref) > 255 or any(ord(character) < 32 for character in ref):
        raise GitHubSourceError("GitHub ref is invalid")
    return ref


class GitHubEvidenceSource:
    """Fetch one explicit UTF-8 file from GitHub and pin it to an immutable commit."""

    def __init__(
        self,
        *,
        token: str,
        maximum_file_bytes: int = _DEFAULT_MAXIMUM_FILE_BYTES,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not token or token != token.strip():
            raise GitHubSourceError("GitHub token is required and must not contain outer whitespace")
        if maximum_file_bytes < 1:
            raise GitHubSourceError("maximum_file_bytes must be positive")
        self.maximum_file_bytes = maximum_file_bytes
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "trustflow-github-evidence-source",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=httpx.Timeout(15.0),
            follow_redirects=False,
            transport=transport,
        )

    def __enter__(self) -> GitHubEvidenceSource:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get_model(
        self,
        endpoint: str,
        model: type[TModel],
        *,
        params: dict[str, str] | None = None,
    ) -> TModel:
        try:
            response = self._client.get(endpoint, params=params)
        except httpx.HTTPError as exc:
            raise GitHubSourceError("GitHub API request failed") from exc
        if response.status_code != 200:
            raise GitHubSourceError(f"GitHub API request failed with status {response.status_code}")
        try:
            return model.model_validate(response.json())
        except (ValidationError, ValueError) as exc:
            raise GitHubSourceError("GitHub API returned an invalid response shape") from exc

    def load_file(
        self,
        *,
        repository: str,
        path: str,
        ref: str,
        identifier: str,
        title: str,
        evidence_owner: str,
        classification: SourceClassification = SourceClassification.INTERNAL,
        approved: bool = False,
    ) -> SourceDocument:
        repository_owner, repository_name = _repository_parts(repository)
        safe_path = _safe_repository_path(path)
        safe_ref = _safe_ref(ref)
        encoded_owner = quote(repository_owner, safe="")
        encoded_repository = quote(repository_name, safe="")
        encoded_ref = quote(safe_ref, safe="")
        encoded_path = quote(safe_path, safe="/")

        commit = self._get_model(
            f"/repos/{encoded_owner}/{encoded_repository}/commits/{encoded_ref}",
            _CommitResponse,
        )
        item = self._get_model(
            f"/repos/{encoded_owner}/{encoded_repository}/contents/{encoded_path}",
            _ContentResponse,
            params={"ref": commit.sha},
        )
        if item.type != "file":
            raise GitHubSourceError("GitHub source must resolve to a regular file")
        if item.size > self.maximum_file_bytes:
            raise GitHubSourceError("GitHub source exceeds the configured size limit")
        if item.encoding != "base64" or item.content is None:
            raise GitHubSourceError("GitHub source is not available as inline file content")

        encoded_content = "".join(item.content.split())
        try:
            raw = base64.b64decode(encoded_content, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise GitHubSourceError("GitHub source content is not valid base64") from exc
        if len(raw) != item.size:
            raise GitHubSourceError("GitHub source size does not match the API metadata")
        if len(raw) > self.maximum_file_bytes:
            raise GitHubSourceError("GitHub source exceeds the configured size limit")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GitHubSourceError("GitHub source must be UTF-8 text") from exc
        if "\x00" in content:
            raise GitHubSourceError("GitHub source appears to be binary content")

        source_uri = (
            f"https://github.com/{encoded_owner}/{encoded_repository}/blob/"
            f"{commit.sha}/{encoded_path}"
        )
        try:
            return SourceDocument(
                id=identifier,
                title=title,
                owner=evidence_owner,
                version=commit.sha,
                content=content,
                source_uri=source_uri,
                classification=classification,
                approved=approved,
                updated_at=commit.commit.committer.date.astimezone(UTC),
            )
        except ValidationError as exc:
            raise GitHubSourceError("GitHub source metadata is invalid") from exc
