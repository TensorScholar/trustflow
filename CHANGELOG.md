# Changelog

## Unreleased

- Added an exact v0.1 compatibility freeze for the public Python, CLI, OpenAPI, model-schema,
  and SQLite surfaces, with cross-Python canonical contract evidence in CI.
- Made local evaluation API response schemas explicit and stopped exposing server-side
  questionnaire source paths through the public questionnaire response.
- Hardened release builds to require version-consistent metadata and the current main tip for
  real tag/manual candidates.
- Added a self-contained Python 3.11/3.12/3.13 release quality matrix, compatibility verification,
  and live GitHub evidence smoke.
- Added independent clean-source double builds, deterministic sdist metadata canonicalization,
  exact retained-artifact comparison, archive payload safety checks, SHA-256 checksums, and
  source-bound release evidence manifests.
- Added a retained-sdist rebuild check requiring the canonical source distribution to reproduce
  the exact retained wheel under the recorded release environment.
- Pinned the release-only Python/frontend/backend toolchain with a retained constraints lock and
  bound exact toolchain provenance into release evidence.
- Configured CodeQL and the retrieval performance probe to run on release-tag pushes.

## 0.1.0rc2

- Made export fail closed when required reviews are missing, rejected, or unresolved.
- Bound review decisions to the exact draft/evidence state and preserved append-only review history.
- Bound questionnaire locations to exact source bytes and blocked stale or ambiguous round-trip export.
- Prevented source-file and destination overwrite and made exports atomic create-if-absent commits.
- Added in-place DOCX table and nested-table export support.
- Hardened XLSX/CSV answer placement against occupied, hidden, merged, or ambiguous targets.
- Hardened Office archive inspection against unsafe paths, duplicates, encryption,
  excessive members, oversized members, corrupt entries, and compression-ratio bombs.
- Bound evidence reuse to both source content and canonical source provenance metadata.
- Expanded deterministic source-change impact findings with questionnaire and latest-review context.
- Added one optional read-only GitHub exact-file evidence source with race-free ref pinning,
  file-level version/freshness semantics, environment-only credentials, and explicit approval.
- Replaced the web adapter's server-local path import with bounded multipart upload storage.
- Moved review input to a JSON request body and stopped exposing local source paths.
- Made SQLite audit-event sequencing transactional under concurrent writers.
- Fixed the CLI web server so the selected database and upload directory are honored.
- Added negative, adversarial, migration, and concurrency regression tests and aligned CI, Docker,
  security documentation, and release metadata.

## 0.1.0rc1

- Added safe multi-format questionnaire import.
- Added evidence source registry, retrieval, drafting, policy gates, reviews, and export.
- Added source-version impact analysis.
- Added SQLite and memory stores, audit verification, metrics, CLI, optional API, tests,
  release evidence, threat model, and Codex handoff.
