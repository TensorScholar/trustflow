# Security model

TrustFlow treats questionnaires and evidence files as untrusted input and externally shared answers as governed output.

## Protected assets

- proprietary questionnaires;
- internal policies and approved answer libraries;
- externally shared claims;
- reviewer identity and decisions;
- source-version history and audit evidence.

## Primary threats

1. malicious Office archives, macros, traversal entries, malformed packages or decompression bombs;
2. spreadsheet formula injection during export;
3. prompt-like instructions embedded in source documents;
4. unsupported, stale, conflicting or sensitive claims escaping review;
5. accidental source-file mutation or partial output;
6. arbitrary server-local file access through the web adapter;
7. concurrent audit writers corrupting sequence or chain integrity;
8. future cross-tenant retrieval or over-privileged enterprise connectors;
9. source changes leaving previously approved answers stale.

## Current controls

- extension and container inspection before document parser libraries receive input;
- rejection of macro-enabled, encrypted, path-traversing, duplicate, corrupt or over-limit Office members;
- file, member, expansion-ratio, page-count and detected-question ceilings;
- spreadsheet formula neutralization;
- evidence-only deterministic generation by default;
- approved/current source filtering;
- sensitivity, staleness and conflict gates;
- fail-closed human-review requirements at service and exporter boundaries;
- same-source-path rejection and atomic destination replacement;
- controlled multipart upload storage for the optional API;
- transactional SQLite audit sequencing with a hash-linked event chain;
- source-version impact scans.

## Risk register

| Risk | Failure mode | Mitigation / required evidence |
| --- | --- | --- |
| Malicious document | Parser receives an unsafe container | Reject unsafe archive/package properties; maintain hostile fixture tests |
| Formula injection | Exported cell is interpreted as a formula | Neutralize dangerous prefixes and verify round trips |
| Review bypass | Sensitive/stale/conflicting/unsupported answer is exported | Fail closed; negative export tests |
| Unsupported claim | Generator invents an answer | Evidence-only generation; unsupported-answer metric |
| Source mutation | Export overwrites or partially corrupts input | Reject source destination; atomic replacement |
| Stale evidence | Old policy remains approved | Version/freshness metadata and impact scans |
| Conflicting evidence | Disagreeing sources produce confident output | Conservative conflict status and human review |
| API file disclosure | Remote caller reads server-local paths | Multipart upload only; generated storage names; response redaction |
| Audit race/tampering | Sequence or history becomes inconsistent | Transactional append, hash chain, concurrency/tamper tests |
| Prompt injection in evidence | Source text attempts to alter system policy | Treat source text strictly as evidence, never executable instruction |
| Cross-tenant leakage | Future hosted search mixes tenants | Tenant isolation must exist before multi-tenant hosting |
| Connector privilege | External connector reads or writes too broadly | Scoped authorization and connector-specific threat review before release |

## Residual risk

TrustFlow does not include an OCR sandbox, malware engine, hosted identity layer, tenant-isolation layer, external audit anchor or enterprise connector credential system. The optional API does not provide the production controls listed in `SECURITY.md`.

These are explicit release boundaries, not implied future guarantees. See [limitations](limitations.md).
