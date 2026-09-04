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
_validate_member_name = getattr(_release_artifacts, "_validate_member_name")
_verify_reproducible = getattr(_release_artifacts, "_verify_reproducible")


def test_release_member_paths_reject_traversal_and_sensitive_payloads() -> None:
    with pytest.raises(SystemExit, match="unsafe distribution member path"):
        _validate_member_name("../customer-data.json")
    with pytest.raises(SystemExit, match="forbidden release payload member"):
        _validate_member_name("trustflow/.env")
    with pytest.raises(SystemExit, match="forbidden release payload member"):
        _validate_member_name("trustflow/private.key")


def test_release_member_paths_accept_normal_package_files() -> None:
    _validate_member_name("trustflow-0.1.0rc2/src/trustflow/domain/models.py")
    _validate_member_name("trustflow-0.1.0rc2/LICENSE")


def test_reproducibility_check_rejects_byte_drift(tmp_path: Path) -> None:
    first = tmp_path / "first.whl"
    second = tmp_path / "second.whl"
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
