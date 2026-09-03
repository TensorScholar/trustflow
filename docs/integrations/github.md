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

The connector also disables HTTPX environment discovery (`trust_env=False`). `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `.netrc`, and ambient certificate/proxy process configuration therefore cannot silently change the connector's credential path. Environments that legitimately require an outbound proxy need a future explicit, reviewable proxy/transport contract rather than implicit process state.

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

`updated_at` is repository provenance, not an independent freshness attestation. Git commit timestamps are supplied by repository history and may be unusual or operator-controlled. TrustFlow can apply deterministic age policy to that metadata, but a passing age check does not independently prove when the underlying policy or control became operationally valid. Higher-assurance deployments need an authoritative source-specific validity/freshness policy outside this adapter.

## Safety boundary

The adapter:

- accepts only an explicit `owner/name` repository and explicit relative file path;
- rejects traversal, backslashes, control characters, directories and non-file entries;
- does not follow HTTP redirects;
- ignores ambient HTTP(S) proxy and `.netrc` environment discovery;
- uses GET requests only against the fixed GitHub API origin;
- accepts inline base64 file content only;
- validates Git object identifiers and API response shapes;
- recomputes the Git blob object identity over decoded bytes and rejects an API payload that does not match the reported blob SHA;
- validates declared size against decoded size;
- hard-caps configured and retrieved files at GitHub's 1 MB inline-content boundary;
- requires UTF-8 text and rejects NUL-containing binary-like content;
- returns sanitized request failures without echoing response bodies or credentials.

The connector does not execute repository content. Retrieved text remains untrusted evidence and goes through the same approval, retrieval, review, provenance, and export controls as locally ingested sources.

## Validation status

Pull-request CI uses a deterministic mocked GitHub HTTP transport to exercise request shape, immutable fetch pinning, file-level version/freshness semantics, unrelated-repository-commit stability, blob-identity verification, credential non-persistence, redirect handling, malformed responses, unsafe locators, size limits, binary content, approval semantics, and ambient-proxy isolation.

After a change reaches `main`, CI also runs a real read-only smoke test against this repository's `SECURITY.md` using the ephemeral GitHub Actions token with `contents: read`. The smoke test exercises the real GitHub API, exact-file fetch, file-history lookup, immutable source URI, and default-unapproved behavior. It is deliberately not run for pull-request-controlled code with a runtime token.

A passing live smoke verifies compatibility and reachability for that GitHub-hosted execution at that point in time. It does **not** prove that an arbitrary organization credential is least-privileged, correctly governed by SSO, valid for a private repository, or operationally rotated. Those remain deployment-specific responsibilities.
