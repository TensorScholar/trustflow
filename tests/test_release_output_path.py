from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest


def _load_release_artifacts_script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_release_artifacts.py"
    spec = spec_from_file_location("trustflow_release_artifacts_output_path", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_release_artifacts = _load_release_artifacts_script()
_resolve_safe_output_directory = _release_artifacts._resolve_safe_output_directory


def test_release_output_directory_accepts_strict_descendant(tmp_path: Path) -> None:
    working_directory = tmp_path / "repo"
    working_directory.mkdir()
    output = working_directory / "dist" / "release"

    assert (
        _resolve_safe_output_directory(
            output,
            working_directory=working_directory,
        )
        == output.resolve()
    )


@pytest.mark.parametrize("target", ["self", "parent", "sibling"])
def test_release_output_directory_rejects_destructive_scope(
    tmp_path: Path,
    target: str,
) -> None:
    working_directory = tmp_path / "repo"
    working_directory.mkdir()
    candidates = {
        "self": working_directory,
        "parent": tmp_path,
        "sibling": tmp_path / "other",
    }

    with pytest.raises(SystemExit, match="strict descendant"):
        _resolve_safe_output_directory(
            candidates[target],
            working_directory=working_directory,
        )


def test_release_output_directory_rejects_parent_traversal(tmp_path: Path) -> None:
    working_directory = tmp_path / "repo"
    working_directory.mkdir()

    with pytest.raises(SystemExit, match="strict descendant"):
        _resolve_safe_output_directory(
            working_directory / "nested" / ".." / "..",
            working_directory=working_directory,
        )
