# Publishing

Before publishing TrustFlow:

1. public CI is green on every supported Python version;
2. Ruff, strict mypy, pytest, branch coverage, pip-audit, architecture/security scans, build,
   Twine metadata validation, and isolated wheel smoke pass;
3. generated schemas match source;
4. release artifacts come from the tagged commit and the worktree is clean;
5. SBOM, manifest, checksums, validation report, source archive, and Git bundle are attached;
6. limitations and status are honest;
7. no real customer data or credentials are present;
8. the tag matches all version-bearing files.

PyPI publication is manual in v0.1.
