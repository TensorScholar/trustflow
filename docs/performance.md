# Performance contract

TrustFlow treats performance evidence the same way it treats product evidence: measurements must be reproducible, scoped, and described without turning a synthetic observation into a production guarantee.

## Current hot path

Questionnaire drafting and source-change revalidation execute many retrieval queries against one stable source snapshot. The lexical scorer still inspects every eligible prepared passage for each query, so query-time work remains proportional to `questions × eligible passages`. The important pre-1.0 optimization is that passage splitting, passage tokenization, source-content hashing, and source-provenance hashing are performed once per workflow snapshot rather than once per question.

The one-off public `retrieve()` function remains backward compatible and intentionally behaves as a cold path. `TrustFlowService.draft()` and `TrustFlowService.revalidate()` use the prepared multi-query path.

## Synthetic performance probe

`python scripts/run_performance_probe.py` creates a deterministic corpus with:

- 48 approved synthetic sources;
- 24 passages per source;
- 160 deterministic questions;
- three same-process repetitions;
- Python 3.12 in the dedicated CI workflow.

For every run, the probe requires the cold and prepared paths to emit the same deterministic result checksum. It then compares median elapsed time in the same process. Prepared timing includes building the prepared source snapshot.

The release guard requires at least a conservative `2.0×` same-process speedup on this fixed workload. This threshold is a regression detector, not an SLA. It is deliberately much lower than the improvement observed while introducing the optimization so normal hosted-runner variation does not turn wall-clock noise into a release decision.

## Evidence language

Performance-probe results are **SYNTHETICALLY OBSERVED**. They do not establish customer latency, throughput, concurrency, capacity, hosted-service performance, or production SLOs. Cross-run wall-clock numbers from different hosted runners should not be compared as if the hardware were controlled; the same-process ratio is the primary regression signal.

## Memory and security boundary

Prepared passages and token sets exist only for the duration of a draft or revalidation call. TrustFlow does not use a process-global retrieval cache, so the optimization does not intentionally extend the lifetime of confidential source content beyond the workflow/store lifecycle. The prepared representation consumes additional transient memory proportional to the source passages and token sets.

## Remaining scaling boundary

This is not a vector index, search service, or distributed retrieval engine. Very large evidence registries still require scanning all eligible prepared passages per question. Before replacing the current inspectable lexical implementation, TrustFlow needs prospective workload evidence showing that this remaining complexity is a real bottleneck and that a replacement preserves applicability, provenance, conflict, and deterministic governance semantics.
