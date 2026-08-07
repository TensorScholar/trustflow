# Roadmap and success metrics

## Current `0.1` baseline

- deterministic offline-first workflow;
- strict domain and adapter contracts;
- fixture-based evaluation and adversarial document tests;
- safe persistence and hash-linked audit evidence;
- CLI and optional API;
- reviewable release and validation evidence.

## After external review

Priorities are deliberately narrow:

1. run a real pilot using sanitized, synthetic or customer-approved data;
2. add at most one narrowly scoped enterprise connector with an explicit authorization model;
3. fix reliability and usability problems demonstrated by pilot evidence;
4. stabilize the `0.1.0` release without expanding into a generic automation platform.

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
