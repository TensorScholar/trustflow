from __future__ import annotations

import os
import re

from trustflow.adapters.github_source import GitHubEvidenceSource

_GIT_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def main() -> None:
    token = _required_environment("GITHUB_TOKEN")
    repository = _required_environment("GITHUB_REPOSITORY")
    commit_sha = _required_environment("GITHUB_SHA")

    with GitHubEvidenceSource(token=token) as connector:
        source = connector.load_file(
            repository=repository,
            path="SECURITY.md",
            ref=commit_sha,
            identifier="ci-github-security-policy",
            title="TrustFlow SECURITY.md",
            evidence_owner="maintainers",
        )

    if source.approved:
        raise SystemExit("live GitHub evidence source must remain unapproved by default")
    if "# Security policy" not in source.content:
        raise SystemExit("live GitHub evidence source content did not match SECURITY.md")
    if not _GIT_SHA.fullmatch(source.version):
        raise SystemExit("live GitHub evidence source version was not an immutable Git commit SHA")
    expected_uri = f"https://github.com/{repository}/blob/{source.version}/SECURITY.md"
    if source.source_uri != expected_uri:
        raise SystemExit("live GitHub evidence source URI was not pinned to its file revision")

    print(
        "live GitHub evidence smoke passed: "
        f"source_version={source.version} updated_at={source.updated_at.isoformat()}"
    )


if __name__ == "__main__":
    main()
