# Changelog

## 0.1.0rc2

- Made export fail closed when required reviews are missing, rejected, or unresolved.
- Prevented source-file overwrite and made all exports atomic.
- Added in-place DOCX table and nested-table export support.
- Hardened Office archive inspection against unsafe paths, duplicates, encryption,
  excessive members, oversized members, corrupt entries, and compression-ratio bombs.
- Replaced the web adapter's server-local path import with bounded multipart upload storage.
- Moved review input to a JSON request body and stopped exposing local source paths.
- Made SQLite audit-event sequencing transactional under concurrent writers.
- Fixed the CLI web server so the selected database and upload directory are honored.
- Added negative and concurrency regression tests and aligned CI, Docker, and release metadata.

## 0.1.0rc1

- Added safe multi-format questionnaire import.
- Added evidence source registry, retrieval, drafting, policy gates, reviews, and export.
- Added source-version impact analysis.
- Added SQLite and memory stores, audit verification, metrics, CLI, optional API, tests,
  release evidence, threat model, and Codex handoff.
