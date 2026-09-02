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
- the optional API has no authentication, authorization, tenant isolation, rate limiting, or DLP
  and must not be exposed as a production service;
- uploaded files are retained locally so later export can preserve the source format;
- PDF parsing has file-size and page-count limits but no process sandbox or malware engine;
- dependency resolution is range-based rather than lockfile-reproducible;
- no production-readiness claim.
