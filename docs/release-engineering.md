# Release engineering

TrustFlow treats release artifacts as evidence-bearing outputs, not as permission to claim production readiness.

## Release-source invariant

A real release build (`v*` tag push or manual release dispatch) must satisfy all of the following:

- the requested tag is exactly `v<project.version>`;
- `pyproject.toml`, `src/trustflow/_version.py`, `CITATION.cff`, `CHANGELOG.md`, and the README agree on the release version where applicable;
- the checked-out source commit is exactly the current `origin/main` tip;
- the worktree is clean;
- the v0.1 compatibility lock verifies.

The main-tip requirement deliberately rejects tags cut from stale, side-branch, or otherwise unmerged commits even when their version text matches.

## Release quality gates

The release workflow re-runs its own quality matrix on Python 3.11, 3.12, and 3.13 rather than assuming a prior main workflow was green. Each lane runs formatting/linting, strict typing, architecture, static security, secret scanning, generated-schema drift, the v0.1 compatibility contract, tests/coverage, the demo, and dependency auditing.

The release workflow also runs the live read-only GitHub evidence smoke before building distributions. CodeQL and the retrieval performance probe are configured to run on `v*` tag pushes as independent same-tag checks.

## Reproducible distribution evidence

The build job derives `SOURCE_DATE_EPOCH` from the release source commit and builds the wheel and sdist twice. The build is rejected unless both runs produce the same filenames and byte-identical SHA-256 digests.

Before an artifact is retained, TrustFlow also rejects unsafe archive member paths, link members in the sdist, and obvious sensitive/local payload suffixes such as `.env`, private-key formats, and SQLite/database files.

A successful build bundle contains:

- one wheel;
- one source distribution;
- `SHA256SUMS` for those two distributions;
- `release-evidence.json` binding the package version, expected tag, source commit, source epoch, v0.1 compatibility lock, artifact sizes, and artifact SHA-256 digests.

The bundle is stored as a GitHub Actions artifact. Artifact ZIP container digests are not treated as distribution hashes because container metadata can change independently of the files inside it.

## Dry-run behavior

Pull requests that change release-critical files run the release workflow in dry-run mode. A dry run exercises the same quality, live-source smoke, double-build, archive-safety, checksum, install, and smoke-test path but does not require a tag and does not publish anything.

Manual workflow dispatch remains build-only. It requires an explicit candidate tag and the selected source must still be the current main tip.

## Non-claims and publication boundary

This phase does not create GitHub Releases, tags, or PyPI uploads. It does not add a production-readiness claim, signing authority, customer validation, or a trusted-publisher configuration.

A successful release-evidence build means the package artifacts are reproducibly derived from an eligible source commit and passed the stated engineering gates. It is not authorization to publish a stable release. Stable publication remains gated separately, including prospective external validation and final release review.
