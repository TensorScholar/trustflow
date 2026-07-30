# Architecture

TrustFlow is a modular monolith with hexagonal boundaries.

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

Dependency rules:

- domain has no document-library, SQLite, FastAPI, or vendor dependency;
- application depends on domain and ports;
- adapters implement parsing, export, storage, and generation;
- adapters do not call one another through hidden global state;
- all side effects are visible in the composition root.

The document parser registry is intentionally explicit. A new format needs safety rules,
parser tests, exporter behavior, limitations, and fixture coverage.
