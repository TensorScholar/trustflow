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
- Ruff, strict mypy, pytest/coverage, security checks, schema reproducibility, demo and `pip-audit` must pass;
- build artifacts and metadata must be validated from the release commit;
- version-bearing files and the release tag must agree;
- no customer data, credentials or machine-local artifacts may be included;
- release notes must state residual limitations accurately.

PyPI publication remains manual for the `0.1` line.

## Conduct

Be professional, specific and evidence-driven. Do not publish private customer material, credentials, exploit details, harassment or discriminatory content in repository discussions.
