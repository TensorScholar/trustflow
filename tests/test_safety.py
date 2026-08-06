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


def _minimal_xlsx(archive: zipfile.ZipFile) -> None:
    archive.writestr("[Content_Types].xml", b"<Types/>")
    archive.writestr("xl/workbook.xml", b"<workbook/>")


def test_office_archive_path_traversal_rejected(tmp_path) -> None:
    path = tmp_path / "x.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        _minimal_xlsx(archive)
        archive.writestr("../escape", b"x")
    with pytest.raises(UnsafeDocumentError, match="unsafe member path"):
        inspect_document(path, PolicySettings())


def test_office_archive_excessive_compression_ratio_rejected(tmp_path) -> None:
    path = tmp_path / "x.xlsx"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _minimal_xlsx(archive)
        archive.writestr("xl/large.bin", b"0" * 100_000)
    with pytest.raises(UnsafeDocumentError, match="compression ratio"):
        inspect_document(path, PolicySettings(maximum_compression_ratio=2))


def test_empty_document_rejected(tmp_path) -> None:
    path = tmp_path / "x.csv"
    path.touch()
    with pytest.raises(UnsafeDocumentError, match="empty"):
        inspect_document(path, PolicySettings())
