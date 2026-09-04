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

The release dry run runs on every pull request. This is intentional: package source, documentation, schemas, examples, scripts, tests, and top-level packaging metadata can all affect the source distribution, so a selective path filter could silently skip a release-impacting change.

## Reproducible distribution evidence

The build job derives `SOURCE_DATE_EPOCH` from the exact source commit. It creates two independent tracked-only source snapshots from that commit, normalizes their filesystem modification times to the source epoch, and builds a wheel and sdist from each snapshot in separate build invocations.

The current setuptools sdist backend does not make raw `.tar.gz` output byte-reproducible from `SOURCE_DATE_EPOCH` alone. TrustFlow therefore does **not** claim that the raw backend sdist is reproducible. Before retention, each raw sdist is validated and canonically rewritten as a PAX tar/gzip archive with deterministic non-payload metadata:

- lexicographic member order;
- member and gzip timestamps fixed to `SOURCE_DATE_EPOCH`;
- numeric owner/group IDs fixed to zero;
- textual owner/group names removed;
- directories normalized to mode `0755`;
- regular files normalized to `0755` only when the source member is executable, otherwise `0644`;
- nonessential per-run PAX metadata removed.

Canonicalization is fail-closed: member paths, member types, and link policy are validated before and after the rewrite, and the exact member set, member type, file size, and file payload SHA-256 values must remain unchanged. A payload difference cannot be normalized into a pass.

After canonicalization, both independently built distribution sets must have the same filenames and byte-identical SHA-256 digests. The retained canonical sdist is then used as a source input to build another wheel, and that wheel must be byte-identical to the retained wheel. This checks that canonicalization preserved a buildable source distribution, not merely a stable archive.

This is a deliberately scoped claim: TrustFlow proves same-run repeatability from two independent source snapshots under the recorded GitHub Actions environment. It does not claim universal cross-platform, cross-Python, or cross-toolchain reproducibility.

Before an artifact is retained, TrustFlow also rejects absolute/traversal/ambiguous archive member paths, duplicate members, link or unsupported members in the sdist, and obvious sensitive/local payload suffixes such as `.env`, private-key formats, and SQLite/database files.

A successful build bundle contains:

- one wheel;
- one canonical source distribution;
- `SHA256SUMS` for those two distributions;
- `release-evidence.json` binding the package version, expected tag, source commit, source epoch, v0.1 compatibility lock, raw-build equality observations, the sdist normalization policy, artifact sizes, and retained artifact SHA-256 digests.

The bundle is stored as a GitHub Actions artifact. Artifact ZIP container digests are not treated as distribution hashes because container metadata can change independently of the files inside it.

## Dry-run behavior

Every pull request runs the release workflow in dry-run mode. A dry run exercises the same quality, live-source smoke, independent double-build, sdist normalization, exact retained-artifact comparison, canonical-sdist rebuild, archive-safety, checksum, install, and smoke-test path but does not require a tag and does not publish anything.

Manual workflow dispatch remains build-only. It requires an explicit candidate tag and the selected source must still be the current main tip.

## Non-claims and publication boundary

This phase does not create GitHub Releases, tags, or PyPI uploads. It does not add a production-readiness claim, signing authority, customer validation, or a trusted-publisher configuration.

A successful release-evidence build means the retained package artifacts are deterministically derived from an eligible source commit under the recorded same-run build environment and passed the stated engineering gates. It is not authorization to publish a stable release. Stable publication remains gated separately, including prospective external validation and final release review.
