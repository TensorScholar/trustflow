# TrustFlow Codex handoff task

Act as a senior applied-AI engineer, document-processing engineer, product engineer,
security reviewer, and release engineer.

## Goal

Independently audit and harden `candidate-source/` while preserving the core rule:
**No evidence, no external claim.**

## Constraints

- Work only in `candidate-source`.
- Create local branch `review/trustflow-v0.1`.
- Do not push, merge, tag, publish, open a PR, or modify GitHub.
- Do not add LangChain, a hosted vector database, microservices, Kubernetes, Redis,
  Celery, OCR, or browser extensions.
- Do not add a network LLM requirement.
- Do not weaken strict models, tests, file safety, or coverage.
- Do not claim production readiness.

## Required audit

1. Verify Git and source integrity.
2. Inspect every parser and exporter.
3. Test:
   - malformed Office ZIPs;
   - zip bombs and excessive members;
   - macro payloads;
   - formula injection;
   - path traversal;
   - empty and huge files;
   - nested DOCX tables;
   - XLSX formatting preservation;
   - duplicate questions;
   - missing, stale, conflicting, unapproved, or removed sources;
   - source-version impact;
   - sensitive claims that must never auto-approve;
   - audit mutation;
   - concurrent SQLite writes.
4. Verify that every non-empty generated answer is supported by evidence or an explicit
   human edit.
5. Run Ruff, strict mypy, pytest, branch coverage, pip-audit, build, wheel smoke,
   schema checks, compileall, demo, document round trips, and API smoke.
6. Keep fixes minimal and evidence-driven.
7. Produce local commits and a final review export with raw logs, Git bundle, source ZIP,
   diff, wheel, sdist, SBOM, manifest, and checksums.

## Definition of done

- deterministic offline demo;
- unsupported questions are unanswerable, not hallucinated;
- sensitive claims require review;
- source changes identify affected answers;
- spreadsheet formulas are neutralized;
- strict schemas reject unknown fields;
- clean wheel installation;
- working tree clean;
- nothing published.

Stop after creating the review export.
