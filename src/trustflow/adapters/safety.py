"""Document safety checks."""

from __future__ import annotations

import csv
import zipfile
from pathlib import Path

from trustflow.domain.errors import UnsafeDocumentError
from trustflow.domain.models import DocumentFormat, PolicySettings

_ALLOWED = {item.value for item in DocumentFormat}
_MACRO_MEMBERS = {"vbaProject.bin", "macros/"}


def detect_format(path: Path) -> DocumentFormat:
    suffix = path.suffix.casefold().lstrip(".")
    if suffix not in _ALLOWED:
        raise UnsafeDocumentError(f"unsupported file extension: {path.suffix}")
    return DocumentFormat(suffix)


def inspect_document(path: Path, policy: PolicySettings) -> DocumentFormat:
    if not path.is_file():
        raise UnsafeDocumentError("document does not exist")
    if path.stat().st_size > policy.maximum_file_bytes:
        raise UnsafeDocumentError("document exceeds configured size limit")
    fmt = detect_format(path)
    if fmt in {DocumentFormat.XLSX, DocumentFormat.DOCX}:
        try:
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                if len(members) > policy.maximum_archive_members:
                    raise UnsafeDocumentError("archive contains too many members")
                total = sum(item.file_size for item in members)
                if total > policy.maximum_uncompressed_bytes:
                    raise UnsafeDocumentError("archive expands beyond configured limit")
                names = {item.filename.casefold() for item in members}
                if any(
                    token.casefold() in name
                    for name in names
                    for token in _MACRO_MEMBERS
                ):
                    raise UnsafeDocumentError("macro-enabled office content is not accepted")
        except zipfile.BadZipFile as exc:
            raise UnsafeDocumentError("office document is not a valid ZIP container") from exc
    return fmt


def neutralize_spreadsheet_formula(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def safe_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [list(row) for row in csv.reader(handle)]
