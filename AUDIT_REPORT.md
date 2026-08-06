# Canonical audit report

**Project:** TrustFlow
**Canonical version:** `0.1.0rc2`
**Audit date:** 2026-08-06
**Original archive SHA-256:** `bd220be843f39022813abe7b4b0ab63be875376235bb5df3497fb671aca3281e`
**Original Git commit:** `fb9281f1a7af7cb821ebd5afb6911bf7db1ab513`

## Scope and evidence rule

The uploaded ZIP and checksum file were treated as untrusted inputs. The uploaded files were
not modified. The archive was extracted to a separate working directory, the embedded Git
repository was cloned, and all canonical changes were made in that clone.

A gate is marked `PASS` only when direct local evidence was produced. Anything not executed or
not independently verifiable is marked `NOT TESTED` or `UNKNOWN`.

## Integrity results

| Gate | Status | Evidence |
|---|---|---|
| Uploaded ZIP matches supplied SHA-256 | PASS | Computed digest exactly matched the supplied digest. |
| Outer ZIP path safety | PASS | No absolute paths, `..` traversal, duplicate names, symlinks, devices, encryption, or anomalous compression ratio were found. |
| Embedded `HANDOFF_SHA256SUMS` | PASS | Every listed handoff file verified. |
| Embedded release checksums | PASS | Every file listed in `release/SHA256SUMS` verified. |
| Candidate Git object integrity | PASS | `git fsck --full --strict` produced no errors. |
| Candidate worktree integrity | PASS | All 89 tracked files were present; the initial worktree was clean. |
| Source ZIP vs candidate commit | PASS | File set and SHA-256 values were identical. |
| Git bundle vs candidate commit | PASS | Bundle verified as complete and resolved to the same commit. |

These checks prove package consistency, not correctness of the original implementation.

## Confirmed original defects and canonical corrections

### F-001 — Review gate bypass

**Original status:** FAIL
A sensitive answer with `review_required` could be exported without any review. This was
reproduced with an executable test case.

**Canonical correction:** Export is fail closed. `review_required`, `conflict`, and `stale`
answers require `approved` or `edited` review. `unanswerable` answers require an explicit human
edit. The exporter repeats the same validation as defense in depth.

### F-002 — Rejected review exported as final text

**Original status:** FAIL
A `rejected` review's text was selected as the final exported answer.

**Canonical correction:** Rejected reviews always block export and rejected final text is not
retained as an exportable answer.

### F-003 — Arbitrary server-local path import in the web adapter

**Original status:** FAIL
The API accepted a caller-controlled server-local path and returned parsed content and the local
path. When exposed, this created a local file disclosure boundary.

**Canonical correction:** The path endpoint was replaced by bounded multipart upload into a
controlled directory with generated names. The local storage path is omitted from responses.
Review content was moved from URL query parameters to a JSON body.

### F-004 — Source mutation and partial output risk

**Original status:** FAIL
CSV, DOCX, JSON, and PDF-ledger export could target the source path; failed writes could leave a
partial destination.

**Canonical correction:** Same-path and symlink-to-source destinations are rejected. Every
export writes to a temporary file in the destination directory and uses atomic replacement only
after successful completion.

### F-005 — Concurrent SQLite audit sequence race

**Original status:** FAIL by inspection; concurrency coverage was absent.
Audit sequence selection and insertion were separate operations, so concurrent writers could
select the same sequence.

**Canonical correction:** Audit append uses `BEGIN IMMEDIATE`, reads the current head, creates the
next hash-linked event, and inserts it in one transaction with bounded lock retry. A 40-writer
concurrency test verifies chain integrity.

### F-006 — Container/database configuration defects

**Original status:** FAIL by inspection.
The non-root container user could not create the default database under `/app`. The CLI accepted a
database option for `serve` but the Uvicorn factory ignored it.

**Canonical correction:** The container stores the database and uploads under writable `/data`.
The CLI now constructs the app with the selected database and upload directory.

### F-007 — Incomplete Office-container safety boundary

**Original status:** PARTIAL.
The original implementation bounded count and aggregate expansion and rejected macro markers,
but did not reject traversal names, duplicate names, encrypted members, oversized individual
members, excessive per-member compression ratios, corrupt entries, or missing core package
members.

**Canonical correction:** All listed conditions are rejected before parser libraries receive the
file. Empty files, PDF page count, and total detected question count are also bounded.

### F-008 — DOCX table export did not preserve the recorded location

**Original status:** FAIL by behavior.
Table-cell questions were parsed, but answers were appended outside the table.

**Canonical correction:** Table-cell paragraph locations are explicit and recursively support
nested tables. Answers are written back to the recorded paragraph.

### F-009 — Repeat drafting created an unrecoverable duplicate-answer set

**Original status:** FAIL by inspection.
Repeated draft calls created multiple drafts for the same questions, after which export rejected
the count mismatch.

**Canonical correction:** A questionnaire can be drafted once; a repeat call fails explicitly.
Export also validates an exact one-to-one question/answer mapping.

## Canonical validation matrix

| Gate | Status | Result |
|---|---|---|
| Python syntax / `compileall` | PASS | `src`, `tests`, and `scripts` compiled under Python 3.13.5. |
| Pytest | PASS | 57 tests passed. |
| Branch-aware coverage | PASS | 88.17%; configured minimum is 85%. |
| Original bypass reproduction after fix | PASS | Unreviewed and rejected exports were both blocked. |
| XLSX, CSV, DOCX, JSON round trips | PASS | Includes formula neutralization and nested DOCX tables. |
| Hostile Office fixtures | PASS | Macro, malformed ZIP, traversal, compression ratio, empty file, and invalid package cases covered. |
| SQLite persistence | PASS | Round-trip and concurrent audit-chain tests passed. |
| FastAPI smoke | PASS | Health, multipart import, path-input rejection, and local-path redaction passed. |
| Deterministic demo | PASS | Completed export and 10-event valid audit chain. |
| Architecture script | PASS | No forbidden adapter dependencies found in domain/application layers. |
| Static security script | PASS | No configured `eval`, `exec`, pickle-load, or `shell=True` patterns found. |
| Repository secret script | PASS | No configured credential/key patterns found. |
| Schema generation | PASS | Four committed Pydantic schemas regenerated from canonical models. |
| Wheel build | PASS | Built with PEP 517 through `pip wheel --no-build-isolation`. |
| sdist build | PASS | Built with the local setuptools fallback. |
| Wheel archive integrity and metadata | PASS | ZIP CRC, version, Python requirement, package data, and file inventory checked. |
| Installed-wheel smoke | PASS | Imported from isolated venv `site-packages`, version `0.1.0rc2`, demo passed. Runtime dependencies were supplied from the host environment. |
| `git diff --check` | PASS | No whitespace errors. |
| Python line-length check | PASS | No Python line exceeded the configured 100-character limit. |

## Explicitly unverified

| Gate | Status | Reason |
|---|---|---|
| Python 3.11 | NOT TESTED | Interpreter unavailable locally. |
| Python 3.12 | NOT TESTED | Interpreter unavailable locally. |
| Ruff | NOT TESTED | Tool package unavailable in the execution environment. CI is configured to run it. |
| Strict mypy | NOT TESTED | Tool package unavailable in the execution environment. CI is configured to run it. |
| `pip-audit` / current vulnerability database | NOT TESTED | Tool and advisory database were unavailable. No vulnerability-clean claim is made. |
| Clean dependency resolution from public PyPI | NOT TESTED | The package index available to this environment could not resolve build/runtime packages. |
| Locked, reproducible dependency graph | UNKNOWN | The project intentionally has bounded ranges but no lockfile. Exact future resolution can drift. |
| `python -m build` | NOT TESTED | The `build` package was unavailable; PEP 517 `pip wheel` and setuptools sdist fallback passed. |
| Twine metadata check | NOT TESTED | Twine was unavailable. Wheel metadata was inspected directly. |
| Docker build and runtime health check | NOT TESTED | Docker was unavailable. Dockerfile defects were corrected by inspection. |
| GitHub Actions execution | NOT TESTED | No remote repository or runner was used. |
| SBOM for final resolved environment | NOT TESTED | No final lock/resolution exists. A declarative SBOM would be incomplete. |
| Malware engine / parser process sandbox | NOT TESTED | Not implemented; explicitly outside this release boundary. |
| Windows and macOS behavior | NOT TESTED | Linux-only local execution. |
| Real enterprise documents and scale | NOT TESTED | Only included and generated fixtures were used. |
| Production security | UNKNOWN | Authentication, authorization, tenant isolation, encryption at rest, DLP, retention, rate limiting, observability, backup/restore, external audit anchoring, and incident operations are not implemented. |

## Release conclusion

`0.1.0rc2` is a canonical, hardened, testable engineering release candidate suitable for
transfer to GitHub and independent CI review. It is **not production-ready**, and no statement in
this report should be interpreted as a vulnerability-free, compliance-certified, or
production-security guarantee.
