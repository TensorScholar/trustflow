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


def _canonical_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def source_provenance_digest(source: SourceDocument) -> str:
    """Fingerprint governance metadata whose drift must invalidate an evidence snapshot."""
    metadata = source.model_dump(
        mode="json",
        exclude={"applicability", "content", "tags", "updated_at", "valid_until"},
    )
    metadata["tags"] = sorted(source.tags)
    metadata["applicability"] = {
        "products": sorted(source.applicability.products),
        "regions": sorted(source.applicability.regions),
        "deployment_models": sorted(source.applicability.deployment_models),
    }
    metadata["updated_at"] = _canonical_timestamp(source.updated_at)
    metadata["valid_until"] = _canonical_timestamp(source.valid_until)
    payload = json.dumps(
        metadata,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _evidence_snapshot_matches_source(source: SourceDocument, evidence: Evidence) -> bool:
    """Verify redundant evidence metadata still represents the source bound by its digests."""
    return (
        evidence.source_id == source.id
        and evidence.source_title == source.title
        and evidence.source_uri == source.source_uri
        and evidence.source_version == source.version
        and evidence.owner == source.owner
        and evidence.updated_at == source.updated_at
        and evidence.valid_until == source.valid_until
        and evidence.applicability == source.applicability
        and bool(evidence.excerpt.strip())
        and evidence.excerpt in source.content
    )


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
    if not _evidence_snapshot_matches_source(source, evidence):
        return "evidence_snapshot_changed"
    return None
