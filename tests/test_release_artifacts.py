import gzip
import io
import tarfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest


def _load_release_artifacts_script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_release_artifacts.py"
    spec = spec_from_file_location("trustflow_release_artifacts_script", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_release_artifacts = _load_release_artifacts_script()
_canonicalize_sdist = _release_artifacts._canonicalize_sdist
_gzip_header_mtime = _release_artifacts._gzip_header_mtime
_sdist_difference_summary = _release_artifacts._sdist_difference_summary
_tar_manifest = _release_artifacts._tar_manifest
_validate_member_name = _release_artifacts._validate_member_name
_verify_reproducible = _release_artifacts._verify_reproducible


def _write_test_sdist(
    path: Path,
    *,
    gzip_mtime: int,
    member_mtime: int,
    uid: int,
    reverse: bool = False,
) -> None:
    members = [
        ("package", None, 0o775),
        ("package/data.txt", b"payload\n", 0o664),
        ("package/tool.sh", b"#!/bin/sh\nexit 0\n", 0o755),
    ]
    if reverse:
        members.reverse()

    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=gzip_mtime) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                for name, payload, mode in members:
                    info = tarfile.TarInfo(name)
                    info.mtime = member_mtime
                    info.uid = uid
                    info.gid = uid + 1
                    info.uname = f"user-{uid}"
                    info.gname = f"group-{uid}"
                    info.mode = mode
                    info.pax_headers = {
                        "atime": str(member_mtime + 1),
                        "ctime": str(member_mtime + 2),
                    }
                    if payload is None:
                        info.type = tarfile.DIRTYPE
                        info.size = 0
                        archive.addfile(info)
                    else:
                        info.type = tarfile.REGTYPE
                        info.size = len(payload)
                        archive.addfile(info, io.BytesIO(payload))


def _write_link_sdist(path: Path) -> None:
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        link = tarfile.TarInfo("package/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../outside"
        archive.addfile(link)


def test_release_member_paths_reject_traversal_and_sensitive_payloads() -> None:
    with pytest.raises(SystemExit, match="unsafe distribution member path"):
        _validate_member_name("../customer-data.json")
    with pytest.raises(SystemExit, match="unsafe distribution member path"):
        _validate_member_name("package\\customer-data.json")
    with pytest.raises(SystemExit, match="unsafe distribution member path"):
        _validate_member_name("C:/customer-data.json")
    with pytest.raises(SystemExit, match="forbidden release payload member"):
        _validate_member_name("trustflow/.env")
    with pytest.raises(SystemExit, match="forbidden release payload member"):
        _validate_member_name("trustflow/private.key")


def test_release_member_paths_accept_normal_package_files() -> None:
    _validate_member_name("trustflow-0.1.0rc2/src/trustflow/domain/models.py")
    _validate_member_name("trustflow-0.1.0rc2/LICENSE")


def test_reproducibility_check_rejects_byte_drift(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "package.whl"
    second = second_dir / "package.whl"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    with pytest.raises(SystemExit, match="not byte-reproducible"):
        _verify_reproducible({first.name: first}, {second.name: second})


def test_reproducibility_check_rejects_filename_drift(tmp_path: Path) -> None:
    first = tmp_path / "first.whl"
    second = tmp_path / "second.whl"
    first.write_bytes(b"same")
    second.write_bytes(b"same")

    with pytest.raises(SystemExit, match="filenames differ"):
        _verify_reproducible({first.name: first}, {second.name: second})


def test_sdist_diagnostics_identifies_gzip_wrapper_drift(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    first.write_bytes(gzip.compress(b"same tar stream", mtime=1))
    second.write_bytes(gzip.compress(b"same tar stream", mtime=2))

    summary = _sdist_difference_summary(first, second)

    assert "gzip wrapper drift" in summary
    assert "mtime=1 != 2" in summary


def test_sdist_canonicalization_converges_metadata_without_payload_drift(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    _write_test_sdist(first, gzip_mtime=10, member_mtime=20, uid=1000)
    _write_test_sdist(second, gzip_mtime=30, member_mtime=40, uid=2000, reverse=True)

    _canonicalize_sdist(first, source_date_epoch=123)
    _canonicalize_sdist(second, source_date_epoch=123)

    assert first.read_bytes() == second.read_bytes()
    assert _gzip_header_mtime(first) == 123
    manifest = _tar_manifest(first)
    assert list(manifest) == ["package", "package/data.txt", "package/tool.sh"]
    assert manifest["package"]["mode"] == 0o755
    assert manifest["package/data.txt"]["mode"] == 0o644
    assert manifest["package/tool.sh"]["mode"] == 0o755
    for entry in manifest.values():
        assert entry["mtime"] == 123
        assert entry["uid"] == 0
        assert entry["gid"] == 0
        assert entry["uname"] == ""
        assert entry["gname"] == ""
        assert entry["pax_headers"] == []
    assert manifest["package/data.txt"]["payload_sha256"] == _release_artifacts._sha256_bytes(
        b"payload\n"
    )


def test_sdist_canonicalization_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "package.tar.gz"
    _write_test_sdist(path, gzip_mtime=10, member_mtime=20, uid=1000)

    _canonicalize_sdist(path, source_date_epoch=123)
    first = path.read_bytes()
    _canonicalize_sdist(path, source_date_epoch=123)

    assert path.read_bytes() == first


def test_sdist_canonicalization_rejects_links(tmp_path: Path) -> None:
    path = tmp_path / "package.tar.gz"
    _write_link_sdist(path)

    with pytest.raises(SystemExit, match="link member"):
        _canonicalize_sdist(path, source_date_epoch=123)
