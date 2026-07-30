"""Inspectible lexical evidence retrieval."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from trustflow.domain.models import Evidence, PolicySettings, SourceDocument

_TOKEN = re.compile(r"[a-z0-9][a-z0-9_./-]+", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "at", "be", "by", "do", "does", "for", "from",
        "have", "how", "in", "is", "it", "of", "on", "or", "our", "the", "to",
        "what", "when", "where", "which", "who", "with", "you", "your",
    }
)


def _normalize(token: str) -> str:
    value = token.casefold()
    if value.startswith("encrypt"):
        return "encrypt"
    if value.startswith("indemn"):
        return "indemnity"
    return value


def tokenize(text: str) -> frozenset[str]:
    return frozenset(
        normalized
        for token in _TOKEN.findall(text)
        if (normalized := _normalize(token)) not in _STOPWORDS
    )


def retrieve(
    query: str,
    sources: list[SourceDocument],
    policy: PolicySettings,
    *,
    now: datetime | None = None,
    limit: int = 4,
) -> tuple[Evidence, ...]:
    current_time = now or datetime.now(UTC)
    query_tokens = tokenize(query)
    candidates: list[tuple[float, SourceDocument]] = []
    for source in sources:
        if policy.require_approved_sources and not source.approved:
            continue
        if source.valid_until is not None and source.valid_until <= current_time:
            continue
        age_days = max(0, (current_time - source.updated_at).days)
        if age_days > policy.maximum_source_age_days:
            continue
        source_tokens = tokenize(f"{source.title} {source.content} {' '.join(source.tags)}")
        overlap = len(query_tokens & source_tokens)
        if not query_tokens or not overlap:
            continue
        score = overlap / math.sqrt(len(query_tokens) * max(1, len(source_tokens)))
        score = min(1.0, score * 2.2 + 0.08)
        if score < policy.minimum_evidence_score:
            continue
        candidates.append((score, source))
    candidates.sort(key=lambda item: (-item[0], item[1].id))
    return tuple(
        Evidence(
            source_id=source.id,
            source_title=source.title,
            source_uri=source.source_uri,
            source_version=source.version,
            owner=source.owner,
            excerpt=source.content.strip().split("\n", 1)[0][:500],
            score=round(score, 4),
            updated_at=source.updated_at,
            valid_until=source.valid_until,
        )
        for score, source in candidates[:limit]
    )
