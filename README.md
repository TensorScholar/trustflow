# TrustFlow

[![CI](https://github.com/TensorScholar/trustflow/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/TensorScholar/trustflow/actions/workflows/ci.yml)

**Evidence-governed RFP and security-questionnaire automation.**

TrustFlow converts questionnaires into evidence-backed, reviewable claims instead of treating answer generation as an unconstrained text-completion problem.

```text
safe document import -> question extraction -> approved evidence retrieval
-> evidence-only draft -> policy gates -> human review -> safe export
-> source-change impact scan
```

> No evidence, no external claim.

TrustFlow `0.1.0rc2` is a hardened engineering release candidate for demonstration and external review. It is **not a production-ready hosted service**.

## Why TrustFlow

RFP and security-questionnaire workflows fail when generated answers cannot be traced to approved evidence or when sensitive claims bypass review. TrustFlow makes those controls explicit:

- approved, versioned and freshness-aware evidence sources;
- deterministic evidence-only drafting by default;
- mandatory review for sensitive, stale, conflicting or unsupported claims;
- fail-closed export with source-file overwrite protection;
- safe XLSX, DOCX, CSV, JSON, Markdown and text-extractable PDF handling;
- source-change impact analysis across answer/evidence snapshots, including latest review context;
- hash-chained audit events and measurable workflow outcomes.

No API key is required for the default workflow.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[web]'
trustflow demo
```

For development:

```bash
python -m pip install -e '.[dev,web]'
ruff format --check .
ruff check .
mypy src/trustflow
pytest --cov=trustflow --cov-branch
```

CI validates the supported Python 3.11, 3.12 and 3.13 matrix.

## Supported formats

| Format | Import | Export behavior |
| --- | --- | --- |
| XLSX | Yes | Writes answers to worksheet locations; formula-like output is neutralized |
| DOCX | Yes | Writes back to recorded paragraph/table locations |
| CSV | Yes | Writes to adjacent columns with formula neutralization |
| JSON | Yes | Structured questionnaire and claim-ledger output |
| Markdown | Yes | Questions are extracted from lines ending in `?` |
| PDF | Text-extractable only | Source PDF is not mutated; output is a JSON claim ledger |

Macro-enabled or malformed Office containers are rejected before parser libraries receive them. See [format support](docs/formats.md) for the exact boundary.

## Safety model

Export is fail closed. Drafts marked `review_required`, `conflict`, or `stale` require an `approved` or `edited` human review. `unanswerable` drafts have no approved evidence and cannot be promoted to an external claim. Review decisions are bound to the exact draft/evidence snapshot they evaluated.

TrustFlow also rejects attempts to overwrite the imported source questionnaire and commits completed exports with an atomic create-if-absent operation. Evidence reuse is blocked when either source content or source provenance metadata has drifted since retrieval.

See the [security model](docs/security-model.md) and [limitations](docs/limitations.md) before exposing any adapter or API beyond a local evaluation environment.

## Architecture

TrustFlow is a modular monolith with hexagonal boundaries. Domain and application logic remain independent of document libraries, SQLite, FastAPI and other adapter dependencies.

See [architecture](docs/architecture.md) and [ADR 0001](docs/adr/0001-modular-monolith.md).

## Documentation

- [Architecture and integration contracts](docs/architecture.md)
- [Supported document formats](docs/formats.md)
- [Security model and risk register](docs/security-model.md)
- [Known limitations](docs/limitations.md)
- [Roadmap and success metrics](docs/roadmap.md)
- [0.1.0rc2 validation record](docs/audits/0.1.0rc2.md)
- [Security reporting policy](SECURITY.md)
- [Contributing and release discipline](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Release boundary

Included in `0.1.0rc2`: safe import and extraction, evidence registry and retrieval, deterministic drafting, review gates, conflict/staleness handling, safe export, source-content and source-provenance impact scanning, SQLite/in-memory storage, audit verification, metrics, CLI, optional API, tests and release automation.

Not included: OCR, live enterprise connectors, browser extensions, autonomous legal approval, hosted multi-tenancy, authentication/authorization, production DLP/retention controls, or a production-readiness claim.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
