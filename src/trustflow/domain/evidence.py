"""Deterministic evidence identity and revalidation helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from trustflow.domain.models import Evidence, PolicySettings, SourceDocument

_MISSING_DIGEST = "0" * 64


def source_content_digest(content: str) -> str:
    """Return the stable SHA-256 identity of an evidence source body."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def source_provenance_digest(source: SourceDocument) -> str:
    """Fingerprint governance metadata whose drift must invalidate an evidence snapshot."""
    metadata = source.model_dump(mode="json", exclude={"content", "tags"})
    metadata["tags"] = sorted(source.tags)
    payload = json.dumps(
        metadata,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def evidence_invalidation_reason(
    source: SourceDocument,
    evidence: Evidence,
    policy: PolicySettings,
    *,
    now: datetime | None = None,
) -> str | None:
    """Return the deterministic reason an evidence snapshot is no longer reusable."""
    current_time = now or datetime.now(UTC)
    if (
        evidence.source_digest == _MISSING_DIGEST
        or evidence.source_provenance_digest == _MISSING_DIGEST
    ):
        return "source_snapshot_missing"
    if policy.require_approved_sources and not source.approved:
        return "source_revoked"
    if source.version != evidence.source_version:
        return "source_version_changed"
    if source_content_digest(source.content) != evidence.source_digest:
        return "source_content_changed"
    if source.valid_until is not None and source.valid_until <= current_time:
        return "source_expired"
    age_days = max(0, (current_time - source.updated_at).days)
    if age_days > policy.maximum_source_age_days:
        return "source_too_old"
    if source_provenance_digest(source) != evidence.source_provenance_digest:
        return "source_provenance_changed"
    return None
