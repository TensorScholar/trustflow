from __future__ import annotations

import os

from trustflow.adapters.github_source import GitHubEvidenceSource


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
    if not source.source_uri.startswith(f"https://github.com/{repository}/blob/"):
        raise SystemExit("live GitHub evidence source URI was not pinned to GitHub")
    if source.version == commit_sha and "/SECURITY.md" not in source.source_uri:
        raise SystemExit("live GitHub evidence source did not retain file identity")

    print(
        "live GitHub evidence smoke passed: "
        f"source_version={source.version} updated_at={source.updated_at.isoformat()}"
    )


if __name__ == "__main__":
    main()
