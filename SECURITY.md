# Security policy

## Reporting a vulnerability

Do not publish exploit details, credentials, proprietary questionnaires, internal policies or real customer data in a public issue.

Report security-sensitive findings privately to the maintainer through GitHub. A useful report includes the affected version, a minimal reproduction, impact, and any known preconditions. Please avoid destructive testing against systems or data you do not own.

## Security boundary

TrustFlow is a reference implementation and engineering release candidate, not a production-ready hosted service. The optional API is intended for controlled evaluation unless an operator supplies the missing production controls.

The current implementation includes document-container inspection, macro rejection, bounded parsing, spreadsheet formula neutralization, evidence-only drafting, review gates, conflict/staleness handling, source-change impact scans, and hash-chained audit events.

Production deployment still requires controls such as authentication, authorization, tenant isolation, encrypted storage, DLP and retention policy, malware scanning, rate limiting, observability, backup/restore, incident operations, external audit anchoring and connector-specific authorization.

See:

- [Security model and risk register](docs/security-model.md)
- [Known limitations](docs/limitations.md)
- [0.1.0rc2 validation record](docs/audits/0.1.0rc2.md)

No repository document should be interpreted as a vulnerability-free, compliance-certified or production-security guarantee.
