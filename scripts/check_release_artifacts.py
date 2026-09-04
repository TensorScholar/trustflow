"""Verify reproducible release distributions and emit integrity evidence."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

FORBIDDEN_SUFFIXES = (".db", ".env", ".key", ".p12", ".pem", ".sqlite", ".sqlite3")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _gzip_header_mtime(path: Path) -> int | None:
    header = path.read_bytes()[:10]
    if len(header) < 10 or header[:2] != b"\x1f\x8b":
        return None
    return int.from_bytes(header[4:8], "little")


def _tar_manifest(path: Path) -> dict[str, dict[str, object]]:
    manifest: dict[str, dict[str, object]] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            payload_sha256: str | None = None
            if member.isfile():
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise SystemExit(f"unable to inspect sdist member payload: {member.name}")
                payload_sha256 = _sha256_bytes(extracted.read())
            manifest[member.name] = {
                "type": member.type.hex(),
                "size": member.size,
                "mode": member.mode,
                "mtime": member.mtime,
                "uid": member.uid,
                "gid": member.gid,
                "uname": member.uname,
                "gname": member.gname,
                "linkname": member.linkname,
                "pax_headers": sorted(member.pax_headers.items()),
                "payload_sha256": payload_sha256,
            }
    return manifest


def _sdist_difference_summary(first: Path, second: Path) -> str:
    first_tar = gzip.decompress(first.read_bytes())
    second_tar = gzip.decompress(second.read_bytes())
    first_tar_sha = _sha256_bytes(first_tar)
    second_tar_sha = _sha256_bytes(second_tar)
    first_mtime = _gzip_header_mtime(first)
    second_mtime = _gzip_header_mtime(second)
    if first_tar_sha == second_tar_sha:
        return (
            "gzip wrapper drift: "
            f"mtime={first_mtime} != {second_mtime}, uncompressed_tar_sha256={first_tar_sha}"
        )

    first_manifest = _tar_manifest(first)
    second_manifest = _tar_manifest(second)
    first_names = set(first_manifest)
    second_names = set(second_manifest)
    if first_names != second_names:
        return (
            "tar member-set drift: "
            f"only_first={sorted(first_names - second_names)[:10]}, "
            f"only_second={sorted(second_names - first_names)[:10]}"
        )

    metadata_drift: list[str] = []
    payload_drift: list[str] = []
    for name in sorted(first_names):
        first_entry = first_manifest[name]
        second_entry = second_manifest[name]
        if first_entry["payload_sha256"] != second_entry["payload_sha256"]:
            payload_drift.append(name)
        first_metadata = {
            key: value for key, value in first_entry.items() if key != "payload_sha256"
        }
        second_metadata = {
            key: value for key, value in second_entry.items() if key != "payload_sha256"
        }
        if first_metadata != second_metadata:
            metadata_drift.append(name)

    if not metadata_drift and not payload_drift:
        return (
            "tar stream-layout drift with identical member metadata and payloads: "
            f"tar_sha256={first_tar_sha} != {second_tar_sha}, "
            f"gzip_mtime={first_mtime} != {second_mtime}"
        )
    return (
        f"tar drift: metadata={metadata_drift[:10]}, payload={payload_drift[:10]}, "
        f"gzip_mtime={first_mtime} != {second_mtime}"
    )


def _verify_reproducible(first: dict[str, Path], second: dict[str, Path]) -> None:
    if set(first) != set(second):
        raise SystemExit(f"release build filenames differ: {sorted(first)} != {sorted(second)}")
    mismatches = [name for name in sorted(first) if _sha256(first[name]) != _sha256(second[name])]
    if not mismatches:
        return

    diagnostics = [
        f"{name}: {_sdist_difference_summary(first[name], second[name])}"
        for name in mismatches
        if name.endswith(".tar.gz")
    ]
    suffix = f"; diagnostics: {' | '.join(diagnostics)}" if diagnostics else ""
    raise SystemExit(f"release distributions are not byte-reproducible: {mismatches}{suffix}")


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
