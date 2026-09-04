# Contributing

TrustFlow is maintainer-led. Contributions should preserve its evidence-first and fail-closed design rather than broaden scope by default.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,web]'
```

Run the local quality gates before opening a pull request:

```bash
ruff format --check .
ruff check .
mypy src/trustflow
python scripts/check_architecture.py
python scripts/security_scan.py
python scripts/secret_scan.py
python scripts/generate_schemas.py
git diff --exit-code -- schemas
python scripts/check_contract.py
pytest --cov=trustflow --cov-branch
trustflow demo
python -m pip_audit
```

Document-format changes require round-trip fixtures and adversarial/security coverage.

## Security-sensitive changes

A security-sensitive change should include:

1. a concrete threat or failure scenario;
2. a regression test demonstrating the previous failure when practical;
3. the smallest implementation change that closes the boundary;
4. independent review;
5. updated limitations or release notes when residual risk changes.

Do not weaken review gates, archive-safety checks, formula neutralization, path protections, or audit invariants merely to make an input succeed.

## Architecture changes

TrustFlow uses a modular-monolith architecture with hexagonal boundaries. Large changes to dependency direction, persistence boundaries, parser/export contracts, or deployment shape should add or update an ADR under `docs/adr/`.

## Release discipline

Before publishing a release:

- CI must be green on every supported Python version;
- Ruff, strict mypy, pytest/coverage, security checks, schema reproducibility, the v0.1 compatibility contract, demo and `pip-audit` must pass;
- a real candidate tag must match package metadata and point at the current `main` tip;
- the live GitHub evidence smoke must pass on the release source;
- two independent clean source snapshots must produce byte-identical retained wheel/sdist artifacts after deterministic sdist metadata canonicalization;
- sdist canonicalization must preserve the exact member set and payload hashes, and the retained canonical sdist must rebuild the exact retained wheel;
- release distributions must pass archive-safety inspection, `twine check`, wheel install smoke, and SHA-256 checksum generation;
- the retained `release-evidence.json` must bind artifact hashes, normalization policy, and raw-build observations to the exact source commit and compatibility lock;
- CodeQL and the performance probe must pass for a real release tag before publication is authorized;
- no customer data, credentials or machine-local artifacts may be included;
- release notes must state residual limitations accurately.

Every pull request executes the release workflow as a non-publishing dry run because changes across the repository can affect the packaged source distribution. See [release engineering](docs/release-engineering.md) for the exact evidence bundle, normalization boundary, and source eligibility rules.

The reproducibility claim is intentionally limited to repeat builds under the recorded same-run GitHub Actions environment. It is not a universal cross-platform or cross-toolchain reproducibility claim.

PyPI publication remains manual for the `0.1` line and is not authorized merely by a successful build artifact.

## Conduct

Be professional, specific and evidence-driven. Do not publish private customer material, credentials, exploit details, harassment or discriminatory content in repository discussions.
