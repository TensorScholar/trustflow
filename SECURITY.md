# Security policy

## Reporting a vulnerability

Do not publish exploit details, credentials, proprietary questionnaires, internal policies or real customer data in a public issue.

Report security-sensitive findings privately to the maintainer through GitHub. A useful report includes the affected version, a minimal reproduction, impact, and any known preconditions. Please avoid destructive testing against systems or data you do not own.

## Security boundary

TrustFlow is a reference implementation and engineering release candidate, not a production-ready hosted service. The optional API is intended for controlled evaluation unless an operator supplies the missing production controls.

The web adapter is fail-safe by default: `trustflow serve` binds to loopback unless another host is explicitly requested, rejects non-loopback binds unless `--allow-unsafe-remote` is supplied, and the application itself rejects non-loopback clients unless remote access was explicitly enabled. The container default is loopback-only. The unsafe opt-in is an acknowledgement mechanism, not authentication or a production security control.

The current implementation includes document-container inspection, macro rejection, bounded parsing, spreadsheet formula neutralization, evidence-only drafting, review gates, conflict/staleness handling, source-change impact scans, hash-chained audit events, local-only API defaults, no-store security headers, fixed-origin GitHub evidence reads with redirects and ambient proxy discovery disabled, dependency auditing, static security checks, and CodeQL analysis.

Production deployment still requires controls such as authentication, authorization, tenant isolation, encrypted storage, DLP and retention policy, malware scanning, rate limiting, observability, backup/restore, incident operations, external audit anchoring and connector-specific authorization.

See:

- [Security model and risk register](docs/security-model.md)
- [Known limitations](docs/limitations.md)
- [0.1.0rc2 validation record](docs/audits/0.1.0rc2.md)

No repository document should be interpreted as a vulnerability-free, compliance-certified or production-security guarantee.
