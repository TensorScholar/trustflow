"""Verify release distributions and emit reproducibility/integrity evidence."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import re
import shutil
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path, PurePosixPath

FORBIDDEN_SUFFIXES = (".db", ".env", ".key", ".p12", ".pem", ".sqlite", ".sqlite3")
SDIST_NORMALIZATION_VERSION = 1
RELEASE_TOOLCHAIN_DISTRIBUTIONS = (
    "build",
    "packaging",
    "pip",
    "pyproject-hooks",
    "setuptools",
    "twine",
    "wheel",
)
EXACT_CONSTRAINT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)$")


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
    if not name or "\x00" in name or "\\" in name:
        raise SystemExit(f"unsafe distribution member path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"unsafe distribution member path: {name}")
    if path.parts and path.parts[0].endswith(":"):
        raise SystemExit(f"unsafe distribution member path: {name}")
    lowered = name.lower()
    if lowered.endswith(FORBIDDEN_SUFFIXES):
        raise SystemExit(f"forbidden release payload member: {name}")


def _validate_wheel(path: Path) -> None:
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            _validate_member_name(info.filename)
            if info.filename in seen:
                raise SystemExit(f"duplicate wheel member: {info.filename}")
            seen.add(info.filename)


def _validate_sdist(path: Path) -> None:
    seen: set[str] = set()
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            _validate_member_name(member.name)
            if member.name in seen:
                raise SystemExit(f"duplicate sdist member: {member.name}")
            seen.add(member.name)
            if member.issym() or member.islnk():
                raise SystemExit(f"release sdist contains link member: {member.name}")
            if not member.isfile() and not member.isdir():
                raise SystemExit(f"unsupported sdist member type: {member.name}")


def _gzip_header_mtime(path: Path) -> int | None:
    header = path.read_bytes()[:10]
    if len(header) < 10 or header[:2] != b"\x1f\x8b":
        return None
    return int.from_bytes(header[4:8], "little")


def _tar_manifest(path: Path) -> dict[str, dict[str, object]]:
    manifest: dict[str, dict[str, object]] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.name in manifest:
                raise SystemExit(f"duplicate sdist member: {member.name}")
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


def _content_manifest(path: Path) -> dict[str, tuple[str, int, str | None]]:
    manifest = _tar_manifest(path)
    return {
        name: (
            str(entry["type"]),
            int(entry["size"]),
            entry["payload_sha256"] if isinstance(entry["payload_sha256"], str) else None,
        )
        for name, entry in manifest.items()
    }


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


def _normalized_mode(member: tarfile.TarInfo) -> int:
    if member.isdir():
        return 0o755
    return 0o755 if member.mode & 0o111 else 0o644


def _canonicalize_sdist(path: Path, *, source_date_epoch: int) -> None:
    if source_date_epoch < 0:
        raise SystemExit("source date epoch must be non-negative")

    _validate_sdist(path)
    before = _content_manifest(path)
    temporary = path.with_name(f".{path.name}.canonical")
    temporary.unlink(missing_ok=True)

    try:
        with (
            tarfile.open(path, "r:gz") as source,
            temporary.open("wb") as raw_output,
            gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw_output,
                compresslevel=9,
                mtime=source_date_epoch,
            ) as gzip_output,
            tarfile.open(
                fileobj=gzip_output,
                mode="w|",
                format=tarfile.PAX_FORMAT,
            ) as target,
        ):
            for member in sorted(source.getmembers(), key=lambda item: item.name):
                _validate_member_name(member.name)
                if member.issym() or member.islnk():
                    raise SystemExit(f"release sdist contains link member: {member.name}")
                if not member.isfile() and not member.isdir():
                    raise SystemExit(f"unsupported sdist member type: {member.name}")

                normalized = tarfile.TarInfo(member.name)
                normalized.type = tarfile.DIRTYPE if member.isdir() else tarfile.REGTYPE
                normalized.mode = _normalized_mode(member)
                normalized.mtime = source_date_epoch
                normalized.uid = 0
                normalized.gid = 0
                normalized.uname = ""
                normalized.gname = ""
                normalized.pax_headers = {}

                if member.isfile():
                    extracted = source.extractfile(member)
                    if extracted is None:
                        raise SystemExit(f"unable to canonicalize sdist member: {member.name}")
                    payload = extracted.read()
                    normalized.size = len(payload)
                    target.addfile(normalized, io.BytesIO(payload))
                else:
                    normalized.size = 0
                    target.addfile(normalized)

        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

    _validate_sdist(path)
    after = _content_manifest(path)
    if before != after:
        raise SystemExit("sdist canonicalization changed member set or payload content")
    if _gzip_header_mtime(path) != source_date_epoch:
        raise SystemExit("sdist canonicalization did not set deterministic gzip mtime")


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


def _canonical_distribution_name(name: str) -> str:
    return name.lower().replace("_", "-")


def _load_exact_constraints(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"release toolchain constraints file is missing: {path}")

    pins: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = EXACT_CONSTRAINT.fullmatch(line)
        if match is None:
            raise SystemExit(
                "release toolchain constraint must be an exact == pin at "
                f"{path}:{line_number}: {line}"
            )
        name = _canonical_distribution_name(match.group(1))
        if name in pins:
            raise SystemExit(f"duplicate release toolchain constraint: {name}")
        pins[name] = match.group(2)

    expected = set(RELEASE_TOOLCHAIN_DISTRIBUTIONS)
    actual = set(pins)
    if actual != expected:
        raise SystemExit(
            "release toolchain constraints must pin exactly "
            f"{sorted(expected)}; missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
    return dict(sorted(pins.items()))


def _validate_toolchain_versions(
    pins: dict[str, str],
    observed: dict[str, str],
    *,
    python_version: str,
    expected_python_version: str,
) -> None:
    if python_version != expected_python_version:
        raise SystemExit(
            "release Python version mismatch: "
            f"expected {expected_python_version}, observed {python_version}"
        )
    mismatches = {
        name: {"expected": pins[name], "observed": observed.get(name)}
        for name in RELEASE_TOOLCHAIN_DISTRIBUTIONS
        if observed.get(name) != pins[name]
    }
    if mismatches:
        raise SystemExit(f"release toolchain version mismatch: {mismatches}")


def _release_toolchain_evidence(
    constraints_path: Path,
    *,
    expected_python_version: str,
) -> dict[str, object]:
    pins = _load_exact_constraints(constraints_path)
    observed: dict[str, str] = {}
    for distribution in RELEASE_TOOLCHAIN_DISTRIBUTIONS:
        try:
            observed[distribution] = metadata.version(distribution)
        except metadata.PackageNotFoundError as exc:
            raise SystemExit(
                f"release toolchain distribution is not installed: {distribution}"
            ) from exc

    python_version = platform.python_version()
    _validate_toolchain_versions(
        pins,
        observed,
        python_version=python_version,
        expected_python_version=expected_python_version,
    )
    return {
        "python": {
            "expected": expected_python_version,
            "observed": python_version,
        },
        "constraints": {
            "name": constraints_path.name,
            "sha256": _sha256(constraints_path),
            "size_bytes": constraints_path.stat().st_size,
            "pins": pins,
        },
        "observed_distributions": dict(sorted(observed.items())),
        "runner": {
            "os": os.environ.get("RUNNER_OS"),
            "arch": os.environ.get("RUNNER_ARCH"),
            "image_os": os.environ.get("ImageOS"),
            "image_version": os.environ.get("ImageVersion"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-date-epoch", required=True, type=int)
    parser.add_argument("--toolchain-constraints", type=Path, required=True)
    parser.add_argument("--expected-python-version", required=True)
    parser.add_argument("--tag")
    args = parser.parse_args()

    version = _project_version()
    expected_tag = f"v{version}"
    if args.tag is not None and args.tag != expected_tag:
        raise SystemExit(f"tag mismatch: expected {expected_tag}, got {args.tag}")

    toolchain = _release_toolchain_evidence(
        args.toolchain_constraints,
        expected_python_version=args.expected_python_version,
    )
    constraints_sha256 = _sha256(args.toolchain_constraints)

    first = _distribution_files(args.first)
    second = _distribution_files(args.second)
    if set(first) != set(second):
        raise SystemExit(f"release build filenames differ: {sorted(first)} != {sorted(second)}")

    raw_first_hashes = {name: _sha256(path) for name, path in first.items()}
    raw_second_hashes = {name: _sha256(path) for name, path in second.items()}
    raw_byte_equal = {
        name: raw_first_hashes[name] == raw_second_hashes[name] for name in sorted(first)
    }
    raw_sdist_diagnostics = {
        name: _sdist_difference_summary(first[name], second[name])
        for name in sorted(first)
        if name.endswith(".tar.gz") and not raw_byte_equal[name]
    }

    for files in (first, second):
        for name, path in files.items():
            if name.endswith(".whl"):
                _validate_wheel(path)
            else:
                _canonicalize_sdist(path, source_date_epoch=args.source_date_epoch)

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

    constraints_destination = args.output_dir / args.toolchain_constraints.name
    shutil.copy2(args.toolchain_constraints, constraints_destination)
    if _sha256(constraints_destination) != constraints_sha256:
        raise SystemExit("retained release toolchain constraints changed during copy")

    checksum_path = args.output_dir / "SHA256SUMS"
    _write_checksums([*copied, constraints_destination], checksum_path)
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
        "toolchain": toolchain,
        "reproducibility": {
            "scope": (
                "same-run double build from independent source snapshots under the "
                "recorded release toolchain; no cross-platform reproducibility claim"
            ),
            "raw_artifact_sha256": {
                "first": raw_first_hashes,
                "second": raw_second_hashes,
            },
            "raw_artifact_byte_equal": raw_byte_equal,
            "raw_sdist_diagnostics": raw_sdist_diagnostics,
            "retained_artifacts_byte_equal": True,
            "sdist_normalization": {
                "policy_version": SDIST_NORMALIZATION_VERSION,
                "archive_format": "pax",
                "member_order": "lexicographic",
                "member_mtime": args.source_date_epoch,
                "gzip_mtime": args.source_date_epoch,
                "uid": 0,
                "gid": 0,
                "uname": "",
                "gname": "",
                "directory_mode": "0755",
                "regular_file_mode": "0755 when source executable, otherwise 0644",
                "payload_preserved": True,
            },
        },
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
        "release toolchain verified: "
        f"Python {platform.python_version()}, "
        f"pins={toolchain['observed_distributions']}"
    )
    print(f"raw build byte equality: {raw_byte_equal}")
    if raw_sdist_diagnostics:
        print(f"raw sdist diagnostics: {raw_sdist_diagnostics}")
    print(
        "retained release distributions verified: deterministic sdist metadata, "
        f"byte-identical artifacts, archive-safe, checksummed, source={args.source_commit}"
    )


if __name__ == "__main__":
    main()
