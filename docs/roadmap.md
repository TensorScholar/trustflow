# Roadmap and success metrics

## Current `0.1` baseline

- deterministic offline-first workflow;
- strict domain and adapter contracts;
- fixture-based evaluation and adversarial document tests;
- safe persistence and hash-linked audit evidence;
- exact review/evidence provenance binding and source-change impact analysis;
- identity-preserving source-change revalidation with fresh-review enforcement;
- questionnaire-local governance scorecards derived from current persisted state;
- CLI and optional local-only API;
- one narrowly scoped GitHub exact-file evidence integration;
- reviewable release and validation evidence.

## After external review

Priorities remain deliberately narrow:

1. run a real pilot using sanitized, synthetic or customer-approved data;
2. validate the existing GitHub exact-file integration with an operator-controlled, read-only
   credential where appropriate; do not add a second connector without pilot evidence;
3. measure reviewer effort, blocked-risk and revalidation workload against a frozen prospective
   baseline rather than inferring ROI from synthetic fixtures;
4. fix reliability and usability problems demonstrated by pilot evidence;
5. stabilize the `0.1.0` release without expanding into a generic automation platform.

The original connector ceiling has been consumed by the GitHub exact-file source. Broad connector work remains deferred unless a real pilot demonstrates that another system is the dominant workflow bottleneck.

## Operational success metrics

Track metrics that expose the current governance workflow rather than model theatrics:

- current evidence rate;
- external-claim ready and blocked rates;
- review-required count and review completion rate;
- reviewer edit rate;
- revalidation-required answer count/rate and evidence-level impact count;
- time to first draft;
- median current-review turnaround with an explicit sample count.

These are descriptive state/workflow measurements. They do not establish labor savings, ROI, SLA performance or production readiness without a prospective comparator and real external workflow evidence. See [revalidation and governance metrics](revalidation-and-metrics.md) for exact definitions.

## Evaluation metrics

Keep benchmark/evaluation evidence separate from operational telemetry:

- adversarial status accuracy;
- citation precision and recall;
- false-acceptance rate;
- auto-answer precision;
- forbidden-citation rate;
- unsupported-answer rate;
- sensitive auto-approval rate;
- revalidation scenario failures.

Synthetic measurements must be labeled `SYNTHETICALLY OBSERVED`. Prospective pilot measurements must preserve their raw inputs, comparator, run conditions and evidence category.

## Explicitly deferred

- hosted multi-tenant control plane;
- multi-region deployment;
- generic plugin marketplace;
- autonomous high-impact actions;
- broad connector catalog;
- production-readiness or ROI claims without the required external operational evidence.
