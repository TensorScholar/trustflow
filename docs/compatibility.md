# Compatibility contract

TrustFlow treats interface compatibility as release evidence rather than as an assumption. For the `0.1` release line through `0.1.0`, CI applies an exact compatibility freeze to the intentionally exposed surfaces described below.

This is a release-candidate control. It is not a promise that every internal module, database implementation detail, or future major version will remain unchanged forever.

## Frozen v0.1 surfaces

The canonical compatibility manifest covers:

- the package's top-level public Python exports (`trustflow.__all__`), which currently expose only `__version__`;
- CLI command names and their arguments/options, requiredness, multiplicity, choices, and defaults;
- the normalized FastAPI OpenAPI document for the local evaluation API;
- JSON Schema for externally serialized domain/API models used by the current release surface;
- the SQLite table, column, and explicit-index structure exercised by the current store initialization and legacy-review migration path.

Internal Python modules are **not** declared stable public APIs merely because they are importable. Application, domain, adapter, and port modules may evolve while the release is still pre-1.0, provided an intentional change does not violate the frozen external contract.

## Exact freeze policy

Until `v0.1.0` is released, the compatibility gate is intentionally stricter than ordinary semantic-version compatibility. Any canonical surface change—including an additive CLI command, endpoint, response field, model-schema field, or SQLite structural change—changes the contract digest and blocks CI until the change is explicitly reviewed.

The package version embedded in OpenAPI is normalized to `<package-version>`. Moving from an RC version to the stable `0.1.0` version therefore does not by itself constitute interface drift.

The current lock is stored in `compatibility/v0.1-contract.json`. It records the canonical contract byte length and SHA-256 digest, not the entire generated manifest. The full manifest is emitted independently by each supported Python CI lane and uploaded as a short-lived workflow artifact. This keeps the repository lock compact while preserving a human-reviewable representation of the exact proposed contract.

## CI behavior

For Python 3.11, 3.12, and 3.13, CI:

1. runs formatting, lint, typing, architecture, security, secret, and generated-schema checks;
2. emits the current full canonical contract to `.contract/current.json`;
3. uploads that manifest as a workflow artifact;
4. recomputes its byte length and SHA-256 digest;
5. compares the result with the frozen lock;
6. fails closed before tests, demo, and dependency audit if the contract has drifted.

The three supported Python versions must produce the same canonical contract. During the Phase 12 freeze, their full manifests were verified byte-for-byte before the lock was accepted.

CI never updates the lock automatically.

## Intentional contract changes

A contract change must be treated as a release decision, not as a mechanical checksum refresh:

1. inspect the full compatibility artifacts from the failing CI run;
2. identify exactly which Python, CLI, OpenAPI, model-schema, or SQLite surface changed;
3. decide whether the change is intended and appropriate for the current release line;
4. update tests and documentation for the new contract;
5. run `python scripts/check_contract.py --write` to regenerate the compact lock deliberately;
6. review the lock diff and require a fresh full CI run.

`--write` is an explicit maintainer operation. It is not called by CI.

## HTTP API boundary

The FastAPI surface exists for local evaluation and integration testing. Response models are explicit so OpenAPI describes what the evaluation API actually returns, including questionnaire import, draft/revalidation, review decisions, metrics, and governance metrics.

The public questionnaire response intentionally omits the server-side `source_path` field.

This compatibility freeze does **not** turn the evaluation API into a production hosted API. It remains loopback-only by default and does not provide production authentication, authorization, multi-tenancy, DLP, retention, rate limiting, or an SLA.

## SQLite boundary

The contract records the structural SQLite layout created by the current store, including the review-history table and its answer/sequence index. That prevents accidental schema drift inside the `0.1` release line.

It does not establish a general-purpose migration framework or guarantee arbitrary future schema upgrades. Compatibility for a later release that changes persistence semantics must be supported by explicit migration evidence and tests rather than inferred from this structural lock.

## Dependency and generator drift

OpenAPI, JSON Schema, and CLI metadata are generated through dependencies such as FastAPI, Pydantic, Typer, and Click. A dependency-resolution change can therefore alter the canonical contract even when TrustFlow source code appears unchanged. The strict gate catches that drift intentionally. A changed generated contract must be reviewed before acceptance; dependency drift is not an automatic reason to refresh the lock.

## Post-1.0 evolution

TrustFlow does not yet claim a general semantic-version-aware compatibility engine. After the stable release, compatibility policy can evolve from this exact freeze into additive/breaking-change classification if real integration requirements justify that complexity. Until then, the exact freeze is the simpler and safer release control.
