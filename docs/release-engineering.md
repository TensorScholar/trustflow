# Release engineering

TrustFlow treats release artifacts as evidence-bearing outputs, not as permission to claim production readiness.

## Release-source invariant

A real release build (`v*` tag push or manual release dispatch) must satisfy all of the following:

- the requested tag is exactly `v<project.version>`;
- the named Git tag ref exists and dereferences to the checked-out source commit;
- `pyproject.toml`, `src/trustflow/_version.py`, `CITATION.cff`, `CHANGELOG.md`, and the README agree on the release version where applicable;
- the checked-out source commit is exactly the current `origin/main` tip;
- the worktree is clean;
- the v0.1 compatibility lock verifies.

The main-tip and tag-ref requirements deliberately reject tags cut from stale, side-branch, otherwise unmerged, missing, or differently targeted commits even when their version text matches. Annotated tags are dereferenced to their commit before comparison.

## Release quality gates

The release workflow re-runs its own quality matrix on Python 3.11, 3.12, and 3.13 rather than assuming a prior main workflow was green. Each lane runs formatting/linting, strict typing, architecture, static security, secret scanning, generated-schema drift, the v0.1 compatibility contract, tests/coverage, the demo, and dependency auditing.

The release workflow also runs the live read-only GitHub evidence smoke before building distributions. CodeQL and the retrieval performance probe are configured to run on `v*` tag pushes as independent same-tag checks.

The release dry run runs on every pull request. This is intentional: package source, documentation, schemas, examples, scripts, tests, and top-level packaging metadata can all affect the source distribution, so a selective path filter could silently skip a release-impacting change.

## Release-only toolchain lock

Artifact production uses an explicitly frozen release toolchain rather than relying on range resolution at build time. The artifact-producing job uses exact Python `3.12.14` and `release-toolchain-constraints.txt`, which pins the release frontend and PEP 517 build dependencies used by the workflow.

The lock is intentionally release-local. TrustFlow's ordinary `[build-system]` declaration remains compatible with supported setuptools/wheel versions instead of forcing every contributor or downstream builder onto the release runner's exact toolchain. For release evidence, however, the same lock is applied to the frontend environment, each isolated independent build, and the retained-sdist rebuild.

The release verifier fails closed unless the installed release frontend distributions and Python interpreter exactly match the declared release lock. It records the lock SHA-256, exact pins, observed distribution versions, Python version, and available runner identity fields in `release-evidence.json`. The lock file is also carried in the source distribution and retained evidence bundle so the recorded derivation environment is independently inspectable.

## Reproducible distribution evidence

The build job derives `SOURCE_DATE_EPOCH` from the exact source commit. It creates two independent tracked-only source snapshots from that commit, normalizes their filesystem modification times to the source epoch, and builds a wheel and sdist from each snapshot in separate build invocations under the release toolchain lock.

The current setuptools sdist backend does not make raw `.tar.gz` output byte-reproducible from `SOURCE_DATE_EPOCH` alone. TrustFlow therefore does **not** claim that the raw backend sdist is reproducible. Before retention, each raw sdist is validated and canonically rewritten as a PAX tar/gzip archive with deterministic non-payload metadata:

- lexicographic member order;
- member and gzip timestamps fixed to `SOURCE_DATE_EPOCH`;
- numeric owner/group IDs fixed to zero;
- textual owner/group names removed;
- directories normalized to mode `0755`;
- regular files normalized to `0755` only when the source member is executable, otherwise `0644`;
- nonessential per-run PAX metadata removed.

Canonicalization is fail-closed: member paths, member types, and link policy are validated before and after the rewrite, and the exact member set, member type, file size, and file payload SHA-256 values must remain unchanged. A payload difference cannot be normalized into a pass.

After canonicalization, both independently built distribution sets must have the same filenames and byte-identical SHA-256 digests. The retained canonical sdist is then used as a source input to build another wheel under the same release toolchain lock, and that wheel must be byte-identical to the retained wheel. This checks that canonicalization preserved a buildable source distribution, not merely a stable archive.

This is a deliberately scoped claim: TrustFlow proves same-run repeatability from two independent source snapshots under the exact recorded release toolchain and GitHub Actions runner family. It does not claim universal reproducibility across arbitrary platforms, Python versions, runner images, or different build toolchains.

Before an artifact is retained, TrustFlow also rejects absolute/traversal/ambiguous archive member paths, duplicate members, link or unsupported members in the sdist, and obvious sensitive/local payload suffixes such as `.env`, private-key formats, and SQLite/database files.

A successful build bundle contains:

- one wheel;
- one canonical source distribution;
- the exact `release-toolchain-constraints.txt` used by the build;
- `SHA256SUMS` covering the wheel, source distribution, and retained toolchain lock;
- `release-evidence.json` binding the package version, expected tag, source commit, source epoch, v0.1 compatibility lock, exact release toolchain provenance, raw-build equality observations, the sdist normalization policy, artifact sizes, and retained artifact SHA-256 digests.

The bundle is stored as a GitHub Actions artifact. Artifact ZIP container digests are not treated as distribution hashes because container metadata can change independently of the files inside it.

## Dry-run behavior

Every pull request runs the release workflow in dry-run mode. A dry run exercises the same quality, live-source smoke, release-toolchain validation, independent double-build, sdist normalization, exact retained-artifact comparison, canonical-sdist rebuild, archive-safety, checksum, install, and smoke-test path but does not require a tag and does not publish anything.

Manual workflow dispatch remains build-only. It requires an explicit candidate tag; the named tag must exist and dereference to the selected source, and that same source must still be the current main tip.

## Non-claims and publication boundary

This phase does not create GitHub Releases, tags, or PyPI uploads. It does not add a production-readiness claim, signing authority, customer validation, or a trusted-publisher configuration.

A successful release-evidence build means the retained package artifacts are deterministically derived from an eligible source commit under the exact recorded release toolchain and passed the stated engineering gates. It is not authorization to publish a stable release. Stable publication remains gated separately, including prospective external validation and final release review.
