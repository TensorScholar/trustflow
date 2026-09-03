# Limitations

- no OCR;
- no macro-enabled documents;
- no browser extension;
- external evidence integration is limited to one explicit GitHub exact-file reader; there is no
  repository search, broad synchronization, Google Drive, Confluence, Notion, or generic connector
  framework;
- pull-request connector CI uses deterministic mocked API transport; `main` CI adds a real read-only
  GitHub API smoke against this repository using the ephemeral Actions token, but neither proves
  arbitrary organization credentials, SSO policy, private-repository permission scope, or deployment
  network reachability;
- the GitHub connector deliberately ignores ambient HTTP(S) proxy environment configuration to avoid
  silently routing bearer credentials through an operator-unapproved proxy; environments that require
  a proxy need a future explicit connector transport/proxy contract rather than implicit process state;
- GitHub `updated_at` is derived from repository commit metadata and is provenance, not independent
  attestation of when a policy/control became operationally valid; repository-supplied timestamps
  therefore require source-specific governance for higher-assurance freshness claims;
- lexical retrieval is inspectable but not semantic;
- conflict detection is conservative and lexical;
- reviewer values are caller-supplied labels, not authenticated or cryptographically verified
  identities;
- evidence snapshots persisted before source-provenance binding are intentionally untrusted after
  upgrade; affected answers must be redrafted and, when applicable, reviewed again rather than
  inheriting an older approval;
- governed SQLite state mutations and their audit events are committed atomically, but exported
  filesystem artifacts and SQLite audit records are separate resources and do not have a distributed
  transaction or recovery journal tying them together;
- SQLite is single-node; concurrent local writers are serialized, but distributed operation is
  unsupported;
- the optional API has no authentication, authorization, tenant isolation, rate limiting, or DLP;
  loopback-only defaults and remote-client rejection reduce accidental exposure but do not make remote
  hosting safe;
- `--allow-unsafe-remote` is an explicit evaluation-only escape hatch, not an authorization control;
  the API must not be exposed as a production service without the missing controls;
- deployments behind a local reverse proxy can make a remote caller appear local unless the proxy and
  forwarded-client trust boundary are configured correctly; do not use the local-only check as a
  substitute for authentication;
- uploaded files are retained locally so later export can preserve the source format;
- PDF parsing has file-size and page-count limits but no process sandbox or malware engine;
- dependency resolution is range-based rather than lockfile-reproducible;
- CodeQL, Ruff security rules, custom static checks, secret scanning and dependency auditing reduce
  risk but are not a vulnerability-free guarantee;
- repository rulesets are not currently configured; merge governance therefore still depends on
  operator discipline and CI evidence until branch/ruleset enforcement is enabled;
- no production-readiness claim.
