# Limitations

- no OCR;
- no macro-enabled documents;
- no browser extension;
- no live enterprise connectors;
- lexical retrieval is inspectable but not semantic;
- conflict detection is conservative and lexical;
- SQLite is single-node; concurrent local writers are serialized, but distributed operation is
  unsupported;
- the optional API has no authentication, authorization, tenant isolation, rate limiting, or DLP
  and must not be exposed as a production service;
- uploaded files are retained locally so later export can preserve the source format;
- PDF parsing has file-size and page-count limits but no process sandbox or malware engine;
- dependency resolution is range-based rather than lockfile-reproducible;
- no production-readiness claim.
