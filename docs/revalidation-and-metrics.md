# Source-change revalidation and governance metrics

TrustFlow treats external claims as governed snapshots, not reusable prose detached from their evidence state.

## Revalidation contract

`impact-scan` identifies current evidence snapshots that no longer match the source state they were drafted from. Causes include source removal, approval revocation, version/content/provenance drift, expiry and age-policy failure.

`revalidate` converts those findings into a deterministic lifecycle transition for one questionnaire:

1. identify only answers with current impact findings;
2. preserve each affected `answer.id` so claim identity remains stable;
3. retrieve evidence again from current source state and regenerate the draft;
4. persist the replacement answer snapshot atomically with an `answer.revalidated` audit event;
5. preserve all historical reviews unchanged;
6. bind any future review to the new answer digest.

A prior review is therefore historical evidence, not a transferable approval. Its digest no longer matches the revalidated answer and export remains blocked until the current draft satisfies governance again.

If a source-changed answer would otherwise become `answered` automatically, TrustFlow deliberately promotes it to `review_required` and records `source_change_revalidation`. Source change must not silently release a new external assertion.

A successful review also rechecks current evidence before recording approval. If evidence changed between drafting/revalidation and the review action, the review fails rather than creating an approval state that export would immediately invalidate.

A `stale` answer is different from an ordinary reviewable answer. Human approval cannot make invalid evidence current. The evidence source must first be refreshed and the affected answer revalidated. `unanswerable` answers likewise cannot be promoted into evidence-backed external claims through review.

## Human-edit boundary

TrustFlow does not claim semantic verification of arbitrary reviewer-written prose. Allowing unconstrained `edited` text would let a human silently broaden a claim beyond the evidence while retaining the original evidence lineage.

The pre-1.0 fail-closed rule is therefore narrow: an `edited` final claim must match, modulo case and whitespace, one **complete retained evidence excerpt**. A reviewer may select another evidence-backed wording from the retained evidence set, but cannot add prose or trim qualifiers from an excerpt and still inherit the existing governance binding.

`approved` continues to mean the exact generated draft text was accepted unchanged. More flexible human rewriting requires a future deterministic claim-support contract or a new evidence/review cycle; it is not implied by the current `edited` state.

## Commands

Inspect current source impact:

```bash
trustflow impact-scan trustflow.db
```

Revalidate every currently impacted answer in one questionnaire:

```bash
trustflow revalidate \
  --database trustflow.db \
  <questionnaire-id>
```

Limit revalidation to impact caused by one source:

```bash
trustflow revalidate \
  --database trustflow.db \
  --source-id security-policy \
  <questionnaire-id>
```

Inspect the governance scorecard:

```bash
trustflow governance-metrics \
  --database trustflow.db \
  <questionnaire-id>
```

The optional local API exposes equivalent `POST /questionnaires/{id}/revalidate` and `GET /questionnaires/{id}/governance-metrics` routes.

## Governance scorecard semantics

The scorecard is descriptive operational telemetry calculated from persisted TrustFlow state. It is not a benchmark, ROI claim, SLA, model-quality claim or external validation result.

| Metric | Meaning |
| --- | --- |
| `answers` | Current draft count for the questionnaire |
| `auto_answer_rate` | Fraction currently classified `answered` |
| `review_rate` | Fraction currently in a review-resolvable status (`review_required` or `conflict`) |
| `evidence_coverage` | Fraction with at least one evidence snapshot, regardless of whether that snapshot is still current |
| `unanswerable_rate` | Fraction currently hard-blocked as `unanswerable` or `stale` |
| `current_evidence_rate` | Fraction whose complete evidence set still passes current source validation |
| `external_claim_ready_rate` | Fraction that currently satisfies answer-status, current-review binding and evidence-validity gates at answer level |
| `external_claim_blocked_rate` | Complement of `external_claim_ready_rate` |
| `review_required_answers` | Number currently requiring a resolvable human review |
| `review_completed_answers` | Review-required answers whose latest successful review is bound to the current answer digest |
| `review_completion_rate` | `review_completed_answers / review_required_answers`; `1.0` when no review is required |
| `reviewer_edit_rate` | Fraction of current successful reviews that selected an alternative complete retained evidence excerpt rather than approving the generated draft verbatim |
| `revalidation_required_answers` | Unique current answers with one or more source-impact findings |
| `revalidation_required_rate` | `revalidation_required_answers / answers` |
| `impact_findings` | Number of evidence-level current impact findings; one answer can have several |
| `time_to_first_draft_seconds` | Time from questionnaire import to the first persisted current draft snapshot |
| `review_turnaround_samples` | Number of current review-required answers with a successful review bound to the current digest |
| `median_review_turnaround_seconds` | Median time from current draft generation to its current successful review |

`external_claim_ready_rate` is intentionally stricter than `auto_answer_rate`. A draft can look answerable while its evidence has drifted or a stored review is bound to an older snapshot; that claim is not ready.

## What this does not claim

- Revalidation does not determine business materiality of a source change beyond the deterministic invalidation rules already encoded by TrustFlow.
- A human review does not repair expired, revoked or otherwise invalid evidence.
- The evidence-bound edit rule does not provide general semantic entailment or free-form rewriting.
- Turnaround metrics do not prove labor savings without a prospective baseline and independent real workflow data.
- The current scorecard is questionnaire-local and single-node; it is not a hosted analytics or tenant reporting system.
