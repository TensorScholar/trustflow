"""Document safety checks."""

from __future__ import annotations

import csv
import hashlib
import zipfile
from pathlib import Path, PurePosixPath

from trustflow.domain.errors import UnsafeDocumentError
from trustflow.domain.models import DocumentFormat, PolicySettings

_ALLOWED = {item.value for item in DocumentFormat}
_MACRO_MARKERS = ("vbaproject.bin", "macros/")
_REQUIRED_OFFICE_MEMBERS = {
    DocumentFormat.XLSX: {"[content_types].xml", "xl/workbook.xml"},
    DocumentFormat.DOCX: {"[content_types].xml", "word/document.xml"},
}


def detect_format(path: Path) -> DocumentFormat:
    suffix = path.suffix.casefold().lstrip(".")
    if suffix not in _ALLOWED:
        raise UnsafeDocumentError(f"unsupported file extension: {path.suffix}")
    return DocumentFormat(suffix)


def file_sha256(path: Path) -> str:
    """Return a stable SHA-256 fingerprint of the exact questionnaire bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect_office_archive(path: Path, fmt: DocumentFormat, policy: PolicySettings) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > policy.maximum_archive_members:
                raise UnsafeDocumentError("archive contains too many members")
            total = 0
            normalized_names: set[str] = set()
            for member in members:
                pure = PurePosixPath(member.filename)
                if pure.is_absolute() or ".." in pure.parts or "\\" in member.filename:
                    raise UnsafeDocumentError("archive contains an unsafe member path")
                normalized = member.filename.casefold()
                if normalized in normalized_names:
                    raise UnsafeDocumentError("archive contains duplicate member names")
                normalized_names.add(normalized)
                if member.flag_bits & 0x1:
                    raise UnsafeDocumentError("encrypted Office members are not accepted")
                if member.file_size > policy.maximum_member_bytes:
                    raise UnsafeDocumentError("archive member exceeds configured size limit")
                total += member.file_size
                if total > policy.maximum_uncompressed_bytes:
                    raise UnsafeDocumentError("archive expands beyond configured limit")
                if member.file_size:
                    if member.compress_size == 0:
                        raise UnsafeDocumentError("archive member has an invalid compression ratio")
                    ratio = member.file_size / member.compress_size
                    if ratio > policy.maximum_compression_ratio:
                        raise UnsafeDocumentError("archive member compression ratio is excessive")
            if any(marker in name for name in normalized_names for marker in _MACRO_MARKERS):
                raise UnsafeDocumentError("macro-enabled Office content is not accepted")
            required = _REQUIRED_OFFICE_MEMBERS[fmt]
            missing = required - normalized_names
            if missing:
                raise UnsafeDocumentError("Office document is missing required package members")
            bad_member = archive.testzip()
            if bad_member is not None:
                raise UnsafeDocumentError(f"Office document has a corrupt member: {bad_member}")
    except zipfile.BadZipFile as exc:
        raise UnsafeDocumentError("Office document is not a valid ZIP container") from exc


def inspect_document(path: Path, policy: PolicySettings) -> DocumentFormat:
    if not path.is_file():
        raise UnsafeDocumentError("document does not exist")
    size = path.stat().st_size
    if size == 0:
        raise UnsafeDocumentError("document is empty")
    if size > policy.maximum_file_bytes:
        raise UnsafeDocumentError("document exceeds configured size limit")
    fmt = detect_format(path)
    if fmt in {DocumentFormat.XLSX, DocumentFormat.DOCX}:
        _inspect_office_archive(path, fmt, policy)
    return fmt


def neutralize_spreadsheet_formula(value: str) -> str:
    candidate = value.lstrip("\ufeff\t\r\n\v\f ")
    if candidate.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def safe_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [list(row) for row in csv.reader(handle)]
