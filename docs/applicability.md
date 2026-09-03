# Evidence Applicability and Claim Safety

TrustFlow distinguishes **relevant evidence** from **applicable evidence**. A source can be lexically relevant to a questionnaire question and still be unsafe to reuse for the requested external claim.

## Applicability contract

`SourceDocument.applicability` and every derived `Evidence` snapshot may declare three conservative scope dimensions:

- `products`
- `regions`
- `deployment_models`

An empty dimension means **not declared**, not "applies everywhere."

For an explicitly scoped questionnaire question:

1. an explicitly declared source dimension is eligible only when it covers every requested value in that dimension; partial overlap is not sufficient;
2. an explicit source-scope mismatch or incomplete declared coverage makes that source ineligible before answer generation;
3. a matching declared scope remains eligible for the normal evidence, freshness, conflict, confidence, and sensitivity gates;
4. if any evidence retained in the claim lineage leaves a requested dimension undeclared, automatic external-claim approval is blocked with `applicability_unknown:<dimension>` and human review is required;
5. if no applicable approved evidence remains, the answer is `unanswerable` with `no_applicable_evidence`.

The current scope extractor is intentionally conservative. It recognizes only low-ambiguity syntactic forms for product, region, and deployment model. It is not a general semantic parser and it deliberately prefers missed auto-answer opportunities over inventing scope.

## Claim-shape safety

Applicability is necessary but not sufficient. Before an answer can become `answered`, deterministic policy also checks for claim shapes that are dangerous to infer from merely relevant evidence:

- partial support for conjunctive `both ... and ...` claims;
- unsupported universal wording such as `all` or `everywhere`;
- broad predicates such as `secure`, `safe`, `compliant`, or `protected` without a sufficiently specific claim;
- internally contradictory clauses.

These rules are review-biased. They are designed to prevent false external assertions, not to maximize automatic completion rate.

## Provenance and revalidation

Applicability is part of source governance metadata and therefore part of `source_provenance_digest`. Evidence snapshots also retain their applicability scope.

Changing source applicability after a claim was drafted invalidates the prior evidence snapshot as `source_provenance_changed`, making the affected claim eligible for the same source-change impact and revalidation workflow as other governed metadata changes.

JSON evidence-ledger exports include applicability alongside source id, version, digest, and URI so downstream reviewers can inspect the scope that supported the claim.

## External integrations

A connector importing a document does not infer organizational applicability authority. In particular, the GitHub evidence source imports an exact file as unapproved evidence and does not guess product, region, or deployment scope. Approval and applicability remain explicit governance decisions.

## Evaluation evidence

The repository contains a self-authored 16-scenario adversarial corpus for supported, stale, conflicting, partially supported, overbroad, wrong-scope, revoked, ambiguous, contradictory, and source-change cases.

Results from that corpus are **SYNTHETICALLY OBSERVED** only. They are not external validation, customer evidence, or proof that the current deterministic heuristics cover arbitrary real-world questionnaire language.

The CI adversarial gate requires all labeled cases to pass and enforces perfect synthetic status/citation/auto-answer precision and zero synthetic false acceptance, forbidden citations, unsupported auto-answers, and sensitive auto-approval on this frozen corpus. Those thresholds are regression gates for this repository corpus, not claims about real-world accuracy.

The stable-release gate still requires prospective validation on independently authored questionnaire and evidence material.
