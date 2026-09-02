"""Inspectible lexical evidence retrieval."""

from __future__ import annotations

import math
import re
from datetime import datetime

from trustflow.domain.evidence import source_content_digest, source_provenance_digest
from trustflow.domain.models import Evidence, PolicySettings, SourceDocument

_TOKEN = re.compile(r"[a-z0-9][a-z0-9_./-]+", re.IGNORECASE)
_PASSAGE_SPLIT = re.compile(r"(?<=[.!?])(?:\s+|\n+)|\n+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "be",
        "by",
        "do",
        "does",
        "for",
        "from",
        "have",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "our",
        "the",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "with",
        "you",
        "your",
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


def _passages(content: str) -> tuple[str, ...]:
    passages = tuple(part.strip()[:500] for part in _PASSAGE_SPLIT.split(content) if part.strip())
    return passages or (content.strip()[:500],)


def _score(query_tokens: frozenset[str], text: str) -> float:
    text_tokens = tokenize(text)
    overlap = len(query_tokens & text_tokens)
    if not query_tokens or not overlap:
        return 0.0
    score = overlap / math.sqrt(len(query_tokens) * max(1, len(text_tokens)))
    return min(1.0, score * 2.2 + 0.08)


def retrieve(
    query: str,
    sources: list[SourceDocument],
    policy: PolicySettings,
    *,
    limit: int = 4,
    now: datetime | None = None,
) -> tuple[Evidence, ...]:
    # ``now`` remains part of the public pre-1.0 call surface for compatibility. Freshness is
    # intentionally evaluated by the deterministic policy gate rather than filtered out here.
    _ = now
    query_tokens = tokenize(query)
    candidates: list[tuple[float, SourceDocument, str]] = []
    for source in sources:
        if policy.require_approved_sources and not source.approved:
            continue
        scored_passages = [
            (_score(query_tokens, passage), passage) for passage in _passages(source.content)
        ]
        scored_passages = [
            item for item in scored_passages if item[0] >= policy.minimum_evidence_score
        ]
        if not scored_passages:
            continue
        score, excerpt = max(scored_passages, key=lambda item: (item[0], item[1]))
        candidates.append((score, source, excerpt))
    candidates.sort(key=lambda item: (-item[0], item[1].id, item[2]))
    return tuple(
        Evidence(
            source_id=source.id,
            source_title=source.title,
            source_uri=source.source_uri,
            source_version=source.version,
            source_digest=source_content_digest(source.content),
            source_provenance_digest=source_provenance_digest(source),
            owner=source.owner,
            excerpt=excerpt,
            score=round(score, 4),
            updated_at=source.updated_at,
            valid_until=source.valid_until,
        )
        for score, source, excerpt in candidates[:limit]
    )
