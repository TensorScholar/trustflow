# Architecture

TrustFlow is a modular monolith with hexagonal boundaries and a functional-core / imperative-shell bias.

```text
CLI / optional API
        |
application service
        |
domain policy + retrieval
        |
ports
 /      |       \
parsers store   generator
exporters
```

## Dependency rules

- `domain` has no document-library, SQLite, FastAPI or vendor dependency;
- `application` depends on domain types and ports rather than concrete adapters;
- adapters implement parsing, export, persistence and generation;
- adapters do not communicate through hidden global state;
- side effects are assembled at the composition boundary.

The architecture is intentionally one deployable process. Distributed services, brokers and cross-service transactions are deferred until there is evidence that the modular-monolith boundary is insufficient.

## Integration contracts

### Answer generator

Receives a question and approved evidence. It cannot approve claims, query arbitrary sources or export files. The default implementation is deterministic and extractive.

### Parser

Returns stable question IDs plus explicit source locations. Parsers must treat document content as data and must not execute macros or embedded instructions.

### Exporter

Writes final answer text only after application policy allows export. Export adapters repeat critical validation as defense in depth, neutralize formula-like spreadsheet output, reject unsafe source/destination relationships and replace completed output atomically.

### Store

Persistence is exposed through ports. SQLite is the durable single-node implementation; an in-memory store supports deterministic tests and demos.

### Optional web adapter

The API accepts bounded uploads into controlled storage rather than caller-selected server-local paths. It is an adapter over the same application policies and is not a separate trust boundary that may bypass them.

## Document adapters

The parser registry is explicit. A new format requires:

1. a documented safety boundary;
2. deterministic location semantics;
3. parser and exporter tests;
4. hostile/malformed fixture coverage where applicable;
5. an update to `docs/formats.md` and `docs/limitations.md`.

## Architectural decisions

See [ADR 0001: Modular monolith](adr/0001-modular-monolith.md).
