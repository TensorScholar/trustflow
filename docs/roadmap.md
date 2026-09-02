# Roadmap and success metrics

## Current `0.1` baseline

- deterministic offline-first workflow;
- strict domain and adapter contracts;
- fixture-based evaluation and adversarial document tests;
- safe persistence and hash-linked audit evidence;
- exact review/evidence provenance binding and source-change impact analysis;
- CLI and optional API;
- one narrowly scoped GitHub exact-file evidence integration;
- reviewable release and validation evidence.

## After external review

Priorities remain deliberately narrow:

1. run a real pilot using sanitized, synthetic or customer-approved data;
2. validate the existing GitHub exact-file integration with an operator-controlled, read-only
   credential where appropriate; do not add a second connector without pilot evidence;
3. fix reliability and usability problems demonstrated by pilot evidence;
4. stabilize the `0.1.0` release without expanding into a generic automation platform.

The original connector ceiling has been consumed by the GitHub exact-file source. Broad connector work remains deferred unless a real pilot demonstrates that another system is the dominant workflow bottleneck.

## Success metrics

Track metrics that expose workflow quality rather than model theatrics:

- auto-answer rate;
- review rate;
- evidence coverage;
- unanswerable rate;
- unsupported-answer rate;
- sensitive auto-approval rate;
- reviewer edit rate;
- citation recall on a labeled fixture;
- source-change impact count;
- time to first draft.

Synthetic measurements must be labeled synthetic.

## Explicitly deferred

- hosted multi-tenant control plane;
- multi-region deployment;
- generic plugin marketplace;
- autonomous high-impact actions;
- broad connector catalog;
- production-readiness claims without the required operational/security controls.
