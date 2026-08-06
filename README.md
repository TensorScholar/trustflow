# TrustFlow

**Evidence-governed RFP and security questionnaire automation.**

TrustFlow turns a questionnaire into a reviewable claim ledger:

```text
safe document import → question extraction → approved evidence retrieval
→ evidence-only draft → sensitivity and conflict gate → human review → safe export
→ source-change impact scan
```

The product rule is simple:

> No evidence, no external claim.

## Why this project exists

Most RFP demos optimize text generation. TrustFlow focuses on the operational gap:

- file-format handling without executing macros;
- source ownership, version, freshness, and approval;
- visible evidence for every answer;
- mandatory review for security, privacy, legal, and financial claims;
- conflict and stale-source detection;
- export into practical business formats;
- claim impact analysis when source documents change;
- measurable auto-answer, review, evidence, and unsupported-answer rates.

The default generator is deterministic and extractive. No API key is required.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,web]'
trustflow demo
pytest
```

## Export safety boundary

Export is fail closed. Drafts marked `review_required`, `conflict`, or `stale` require an
`approved` or `edited` human review. `unanswerable` drafts require an explicit human edit.
Rejected reviews and attempts to overwrite the source questionnaire are blocked.

## Supported formats

- XLSX
- DOCX
- CSV
- JSON
- Markdown
- text-extractable PDF

Macro-enabled or malformed Office documents are rejected. PDF export is JSON-based in this
release; the original PDF is not mutated.

## Product boundary

Included:

- safe import and question extraction;
- evidence source registry;
- lexical retrieval;
- evidence-only drafts;
- sensitive review gate;
- conflict and staleness handling;
- review records;
- XLSX, DOCX, CSV, and JSON export;
- source-version impact scan;
- SQLite and in-memory storage;
- audit verification;
- metrics, CLI, optional API, tests, and release evidence.

Not included:

- a procurement-portal browser extension;
- live Google Drive, SharePoint, Slack, or CRM connectors;
- OCR for scanned PDFs;
- autonomous legal approval;
- a hosted multi-tenant control plane;
- production-readiness claims.

## Status

**Hardened engineering release candidate for demonstration and external review. Not production-ready.**
