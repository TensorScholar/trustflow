import zipfile

import pytest

from trustflow.adapters.safety import (
    detect_format,
    inspect_document,
    neutralize_spreadsheet_formula,
)
from trustflow.domain.errors import UnsafeDocumentError
from trustflow.domain.models import DocumentFormat, PolicySettings


def test_formula_neutralization() -> None:
    assert neutralize_spreadsheet_formula("=1+1") == "'=1+1"
    assert neutralize_spreadsheet_formula("safe") == "safe"


def test_detect_format(tmp_path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("a", encoding="utf-8")
    assert detect_format(path) is DocumentFormat.CSV


def test_unsupported_extension(tmp_path) -> None:
    path = tmp_path / "x.exe"
    path.write_text("a", encoding="utf-8")
    with pytest.raises(UnsafeDocumentError):
        detect_format(path)


def test_missing_file() -> None:
    with pytest.raises(UnsafeDocumentError):
        inspect_document(__import__("pathlib").Path("/missing"), PolicySettings())


def test_macro_member_rejected(tmp_path) -> None:
    path = tmp_path / "x.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/vbaProject.bin", b"x")
    with pytest.raises(UnsafeDocumentError, match="macro"):
        inspect_document(path, PolicySettings())


def test_invalid_office_zip(tmp_path) -> None:
    path = tmp_path / "x.docx"
    path.write_text("not zip", encoding="utf-8")
    with pytest.raises(UnsafeDocumentError, match="valid ZIP"):
        inspect_document(path, PolicySettings())
