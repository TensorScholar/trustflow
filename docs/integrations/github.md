# GitHub evidence source

TrustFlow includes one deliberately narrow external evidence integration: read one explicit UTF-8 file from one GitHub repository and convert that file-level snapshot into a `SourceDocument`.

It is not repository search, discovery, crawling, synchronization, or a generic connector framework.

## Install

```bash
python -m pip install -e '.[github]'
```

## Authorization boundary

Set the token only through the process environment:

```bash
export TRUSTFLOW_GITHUB_TOKEN='...'
```

Use a repository-scoped credential with read-only access to repository contents. TrustFlow does not request or perform repository writes. The token is sent only as an `Authorization` header to the fixed `https://api.github.com` origin, is never accepted as a CLI argument, is not copied into `SourceDocument`, and is not written to the audit payload.

Credential issuance, rotation, revocation, organization policy, SSO enforcement, and proof that an operator chose least privilege remain deployment responsibilities.

## Ingest one file

```bash
trustflow ingest-github-source \
  --database trustflow.db \
  --identifier security-policy \
  --title 'Security policy' \
  --owner security \
  --repository acme/security-policies \
  --path docs/SECURITY.md \
  --ref main \
  --approved
```

`--approved` is explicit. Without it, the source is stored as unapproved and default retrieval policy will not use it for claims.

## Snapshot semantics

The connector performs three narrowly scoped read-only API operations:

1. resolve the supplied branch, tag, or commit ref to an immutable repository commit SHA;
2. fetch the exact requested file at that resolved commit;
3. query the latest commit, at or before that resolved commit, that touched the exact requested path.

The repository commit is used only to make the fetch race-free. The resulting `SourceDocument.version` is the file-level commit SHA from step 3, and `updated_at` is the committer timestamp of that file-level commit. `source_uri` is a token-free GitHub blob URL pinned to the same file-level commit.

This distinction is intentional. An unrelated commit elsewhere in the repository must not make an unchanged evidence file appear newer or force a false source-version change. Conversely, a real change to the requested path—including a later revert—produces new file history and therefore a new source version/provenance event.

## Safety boundary

The adapter:

- accepts only an explicit `owner/name` repository and explicit relative file path;
- rejects traversal, backslashes, control characters, directories and non-file entries;
- does not follow HTTP redirects;
- uses GET requests only against the fixed GitHub API origin;
- accepts inline base64 file content only;
- validates Git object identifiers and API response shapes;
- validates declared size against decoded size;
- limits files to 1 MB by default;
- requires UTF-8 text and rejects NUL-containing binary-like content;
- returns sanitized request failures without echoing response bodies or credentials.

The connector does not execute repository content. Retrieved text remains untrusted evidence and goes through the same approval, retrieval, review, provenance, and export controls as locally ingested sources.

## Validation status

CI uses a deterministic mocked GitHub HTTP transport to exercise request shape, immutable fetch pinning, file-level version/freshness semantics, unrelated-repository-commit stability, credential non-persistence, redirect handling, malformed responses, unsafe locators, size limits, binary content, and approval semantics.

CI does **not** prove that a real organization credential has the intended repository permissions, that a deployed GitHub API version remains compatible, or that GitHub is reachable from a particular deployment. A credentialed live smoke test is therefore an operational validation step, not a claim made by the automated test suite.
