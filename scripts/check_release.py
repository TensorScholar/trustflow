"""Validate release metadata and source-commit eligibility."""

from __future__ import annotations

import argparse
import re
import subprocess
import tomllib
from pathlib import Path


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _project_version() -> str:
    with Path("pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def validate_release(tag: str | None, *, require_main_tip: bool) -> str:
    version = _project_version()
    expected = f"v{version}"
    if tag is not None and tag != expected:
        raise SystemExit(f"tag mismatch: expected {expected}, got {tag}")

    version_file = Path("src/trustflow/_version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', version_file)
    if match is None or match.group(1) != version:
        raise SystemExit("package version does not match pyproject.toml")

    citation = Path("CITATION.cff").read_text(encoding="utf-8")
    if f'version: "{version}"' not in citation:
        raise SystemExit("CITATION.cff version does not match pyproject.toml")

    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    if re.search(rf"^## {re.escape(version)}$", changelog, flags=re.MULTILINE) is None:
        raise SystemExit(f"CHANGELOG.md has no exact release section for {version}")

    readme = Path("README.md").read_text(encoding="utf-8")
    if f"`{version}`" not in readme:
        raise SystemExit("README.md does not name the package version")

    for path in ("CHANGELOG.md", "CITATION.cff", "README.md", "SECURITY.md"):
        if not Path(path).is_file():
            raise SystemExit(f"missing release file: {path}")

    if require_main_tip:
        head = _git("rev-parse", "HEAD")
        try:
            main_tip = _git("rev-parse", "refs/remotes/origin/main")
        except subprocess.CalledProcessError as exc:
            raise SystemExit("origin/main is unavailable for release source verification") from exc
        if head != main_tip:
            raise SystemExit(f"release source is not current main tip: HEAD={head}, main={main_tip}")

    status = _git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise SystemExit("release worktree is not clean")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--require-main-tip", action="store_true")
    args = parser.parse_args()
    expected = validate_release(args.tag, require_main_tip=args.require_main_tip)
    if args.tag is None:
        print(f"release metadata valid for dry-run candidate {expected}")
    else:
        print(f"release metadata valid for {args.tag}")


if __name__ == "__main__":
    main()
