"""Verify reproducible release distributions and emit integrity evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

FORBIDDEN_SUFFIXES = (".db", ".env", ".key", ".p12", ".pem", ".sqlite", ".sqlite3")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_version() -> str:
    with Path("pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _distribution_files(directory: Path) -> dict[str, Path]:
    files = {
        path.name: path
        for path in directory.iterdir()
        if path.is_file() and (path.suffix == ".whl" or path.name.endswith(".tar.gz"))
    }
    wheels = [name for name in files if name.endswith(".whl")]
    sdists = [name for name in files if name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1 or len(files) != 2:
        raise SystemExit(
            f"expected exactly one wheel and one sdist in {directory}, got {sorted(files)}"
        )
    return files


def _validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"unsafe distribution member path: {name}")
    lowered = name.lower()
    if lowered.endswith(FORBIDDEN_SUFFIXES):
        raise SystemExit(f"forbidden release payload member: {name}")


def _validate_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            _validate_member_name(info.filename)


def _validate_sdist(path: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            _validate_member_name(member.name)
            if member.issym() or member.islnk():
                raise SystemExit(f"release sdist contains link member: {member.name}")


def _verify_reproducible(first: dict[str, Path], second: dict[str, Path]) -> None:
    if set(first) != set(second):
        raise SystemExit(f"release build filenames differ: {sorted(first)} != {sorted(second)}")
    mismatches = [name for name in sorted(first) if _sha256(first[name]) != _sha256(second[name])]
    if mismatches:
        raise SystemExit(f"release distributions are not byte-reproducible: {mismatches}")


def _write_checksums(paths: Iterable[Path], output: Path) -> None:
    lines = [f"{_sha256(path)}  {path.name}" for path in sorted(paths, key=lambda item: item.name)]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-date-epoch", required=True, type=int)
    parser.add_argument("--tag")
    args = parser.parse_args()

    version = _project_version()
    expected_tag = f"v{version}"
    if args.tag is not None and args.tag != expected_tag:
        raise SystemExit(f"tag mismatch: expected {expected_tag}, got {args.tag}")

    first = _distribution_files(args.first)
    second = _distribution_files(args.second)
    _verify_reproducible(first, second)
    for name, path in first.items():
        if name.endswith(".whl"):
            _validate_wheel(path)
        else:
            _validate_sdist(path)

    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    copied: list[Path] = []
    for name in sorted(first):
        destination = args.output_dir / name
        shutil.copy2(first[name], destination)
        copied.append(destination)

    checksum_path = args.output_dir / "SHA256SUMS"
    _write_checksums(copied, checksum_path)
    compatibility_lock = json.loads(
        Path("compatibility/v0.1-contract.json").read_text(encoding="utf-8")
    )
    evidence = {
        "schema_version": 1,
        "project": "trustflow",
        "version": version,
        "expected_tag": expected_tag,
        "release_mode": "tag" if args.tag is not None else "dry-run",
        "source_commit": args.source_commit,
        "source_date_epoch": args.source_date_epoch,
        "compatibility_contract": compatibility_lock,
        "artifacts": {
            path.name: {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
            for path in copied
        },
    }
    evidence_path = args.output_dir / "release-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "release distributions verified: byte-reproducible, archive-safe, checksummed, "
        f"source={args.source_commit}"
    )


if __name__ == "__main__":
    main()
