# Threat model

Protected assets:

- proprietary questionnaires;
- internal policies and approved answers;
- externally shared claims;
- reviewer identity and decisions;
- audit evidence.

Threats:

1. malicious Office archives, macros, decompression bombs, or malformed PDFs;
2. spreadsheet formula injection;
3. prompt injection inside source documents;
4. unsupported or stale claims escaping review;
5. conflicting sources producing a confident answer;
6. source changes leaving approved answers stale;
7. audit tampering;
8. accidental cross-tenant retrieval in a future hosted deployment.

Current controls:

- extension and archive inspection;
- macro rejection;
- archive member and uncompressed-size ceilings;
- formula neutralization;
- evidence-only deterministic generator;
- approved/current source filtering;
- sensitivity and conflict gates;
- source-version impact scan;
- strict immutable schemas;
- hash-chained audit events.

Residual risk:

No malware engine, OCR sandbox, multi-tenant identity layer, external audit anchor, or
connector credential system is included.
