# Security model

TrustFlow treats questionnaires and evidence files as untrusted input and externally shared answers as governed output.

## Protected assets

- proprietary questionnaires;
- internal policies and approved answer libraries;
- externally shared claims;
- reviewer labels and decisions;
- source-version, provenance and audit evidence;
- external-source credentials used by optional adapters.

## Primary threats

1. malicious Office archives, macros, traversal entries, malformed packages or decompression bombs;
2. spreadsheet formula injection during export;
3. prompt-like instructions embedded in source documents;
4. unsupported, stale, conflicting or sensitive claims escaping review;
5. accidental source-file mutation or partial output;
6. arbitrary server-local file access through the web adapter;
7. concurrent audit writers corrupting sequence or chain integrity;
8. external connector credential leakage, redirect exfiltration or over-privileged access;
9. source content or provenance metadata changing while dependent answer snapshots remain trusted;
10. stale review replay after the reviewed draft or evidence snapshot changes;
11. persisted evidence metadata being altered while source fingerprints remain unchanged;
12. governed state committing while its corresponding audit event is lost after a persistence failure;
13. repository-provided timestamps being mistaken for independent freshness attestation;
14. future cross-tenant retrieval mixing tenant data.

## Current controls

- extension and container inspection before document parser libraries receive input;
- rejection of macro-enabled, encrypted, path-traversing, duplicate, corrupt or over-limit Office members;
- file, member, expansion-ratio, page-count and detected-question ceilings;
- spreadsheet formula neutralization;
- evidence-only deterministic generation by default;
- approved/current source filtering;
- sensitivity, staleness and conflict gates;
- fail-closed human-review requirements at service and exporter boundaries;
- review decisions bound to a canonical digest of the exact draft and evidence snapshot;
- append-only review history with the latest recorded decision governing export;
- evidence snapshots bound independently to source content and canonical source provenance metadata;
- redundant evidence metadata and excerpts revalidated against the currently fingerprinted source before export;
- same-source-path rejection and atomic create-if-absent destination commit;
- controlled multipart upload storage for the optional API;
- unit-of-work transactions that commit governed internal state mutations and their audit events together;
- transactional SQLite audit sequencing with a hash-linked event chain;
- deterministic source-content/provenance impact scans with latest review context;
- GitHub evidence reads restricted to an explicit repository/file, fixed API origin, GET-only client,
  no redirect following, environment-only token input, race-free repository commit pinning,
  file-level version/freshness derivation, decoded-byte Git blob verification and explicit source
  approval.

## Risk register

| Risk | Failure mode | Mitigation / required evidence |
| --- | --- | --- |
| Malicious document | Parser receives an unsafe container | Reject unsafe archive/package properties; maintain hostile fixture tests |
| Formula injection | Exported cell is interpreted as a formula | Neutralize dangerous prefixes and verify round trips |
| Review bypass | Sensitive/stale/conflicting/unsupported answer is exported | Fail closed; negative export tests |
| Review replay | An old approval is reused after draft/evidence mutation | Bind decision to exact answer-state digest; preserve review history; fail closed on mismatch |
| Evidence snapshot tampering | Stored source URI, owner, title, timestamps or excerpt no longer represent the fingerprinted source | Revalidate redundant snapshot metadata and excerpt against the current source after content/provenance fingerprint checks; fail closed on inconsistency |
| Audit omission | Source, questionnaire, draft or review state commits but the matching audit append fails | Commit governed state and matching audit events in one store transaction; inject audit failures and assert rollback |
| Unsupported claim | Generator invents an answer | Evidence-only generation; unsupported-answer metric |
| Source mutation | Export overwrites or partially corrupts input | Bind locations to source digest; reject source destination; atomic no-overwrite commit |
| Provenance drift | Source owner, URI, classification, freshness, validity or other metadata changes without content/version change | Bind exact non-content source metadata to a canonical provenance digest; invalidate dependent evidence on drift |
| Stale evidence | Old policy remains approved | Version/freshness metadata and impact scans |
| Conflicting evidence | Disagreeing sources produce confident output | Conservative conflict status and human review |
| API file disclosure | Remote caller reads server-local paths | Multipart upload only; generated storage names; response redaction |
| Audit race/tampering | Sequence or history becomes inconsistent | Transactional append, hash chain, concurrency/tamper tests |
| Prompt injection in evidence | Source text attempts to alter system policy | Treat source text strictly as evidence, never executable instruction |
| GitHub credential leakage | Token appears in CLI history, stored source, error body or redirect target | Environment-only token, token-free source/audit metadata, sanitized errors, redirects disabled |
| GitHub overreach | Connector browses or mutates more repository data than intended | Exact repository/file locator; three scoped GETs for ref resolution, exact-file fetch and path history; operator-provided read-only repository credential |
| GitHub payload inconsistency | Decoded file bytes do not correspond to the content API's reported Git object | Recompute the Git blob object identity over decoded bytes and fail closed on mismatch |
| False GitHub freshness | Unrelated repository commits make unchanged evidence look newer or changed | Derive `version` and `updated_at` from the latest commit that touched the exact path, while using the resolved repository commit only to pin the fetch |
| Unattested GitHub freshness | Repository commit time is treated as independent proof of policy/control validity | Label commit time as source provenance only; require authoritative source-specific validity semantics for higher-assurance freshness claims |
| Cross-tenant leakage | Future hosted search mixes tenants | Tenant isolation must exist before multi-tenant hosting |

## Residual risk

TrustFlow does not include an OCR sandbox, malware engine, hosted identity layer, tenant-isolation layer, external audit anchor or connector credential-management system. The GitHub adapter cannot prove that the supplied credential is least-privileged, correctly governed by organization SSO, or rotated appropriately; those remain deployment responsibilities. Git commit timestamps are repository-supplied provenance and are not independent evidence of operational validity. Reviewer values are caller-supplied labels rather than authenticated identities. Exported filesystem artifacts and SQLite audit records remain separate resources without a distributed transaction or recovery journal. The optional API does not provide the production controls listed in `SECURITY.md`.

These are explicit release boundaries, not implied future guarantees. See [limitations](limitations.md).
