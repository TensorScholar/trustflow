"""Inspectible lexical evidence retrieval with deterministic applicability gating."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime

from trustflow.domain.claim_safety import infer_claim_scope, source_matches_claim_scope
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


@dataclass(frozen=True, slots=True)
class PreparedPassage:
    text: str
    tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class PreparedSource:
    source: SourceDocument
    passages: tuple[PreparedPassage, ...]
    content_digest: str
    provenance_digest: str


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


def _score_tokens(query_tokens: frozenset[str], text_tokens: frozenset[str]) -> float:
    overlap = len(query_tokens & text_tokens)
    if not query_tokens or not overlap:
        return 0.0
    score = overlap / math.sqrt(len(query_tokens) * max(1, len(text_tokens)))
    return min(1.0, score * 2.2 + 0.08)


def _score(query_tokens: frozenset[str], text: str) -> float:
    return _score_tokens(query_tokens, tokenize(text))


def prepare_sources(sources: list[SourceDocument]) -> tuple[PreparedSource, ...]:
    """Prepare an immutable source snapshot for repeated retrieval calls."""
    return tuple(
        PreparedSource(
            source=source,
            passages=tuple(
                PreparedPassage(text=passage, tokens=tokenize(passage))
                for passage in _passages(source.content)
            ),
            content_digest=source_content_digest(source.content),
            provenance_digest=source_provenance_digest(source),
        )
        for source in sources
    )


def retrieve_prepared(
    query: str,
    sources: tuple[PreparedSource, ...],
    policy: PolicySettings,
    *,
    limit: int = 4,
    now: datetime | None = None,
) -> tuple[Evidence, ...]:
    """Retrieve evidence from a prepared immutable source snapshot."""
    # ``now`` remains part of the public pre-1.0 call surface for compatibility. Freshness is
    # intentionally evaluated by the deterministic policy gate rather than filtered out here.
    _ = now
    query_tokens = tokenize(query)
    claim_scope = infer_claim_scope(query)
    candidates: list[tuple[float, PreparedSource, str]] = []
    for prepared in sources:
        source = prepared.source
        if policy.require_approved_sources and not source.approved:
            continue
        if not source_matches_claim_scope(claim_scope, source.applicability):
            continue
        scored_passages = [
            (_score_tokens(query_tokens, passage.tokens), passage.text)
            for passage in prepared.passages
        ]
        scored_passages = [
            item for item in scored_passages if item[0] >= policy.minimum_evidence_score
        ]
        if not scored_passages:
            continue
        score, excerpt = max(scored_passages, key=lambda item: (item[0], item[1]))
        candidates.append((score, prepared, excerpt))
    candidates.sort(key=lambda item: (-item[0], item[1].source.id, item[2]))
    return tuple(
        Evidence(
            source_id=prepared.source.id,
            source_title=prepared.source.title,
            source_uri=prepared.source.source_uri,
            source_version=prepared.source.version,
            source_digest=prepared.content_digest,
            source_provenance_digest=prepared.provenance_digest,
            owner=prepared.source.owner,
            excerpt=excerpt,
            score=round(score, 4),
            updated_at=prepared.source.updated_at,
            valid_until=prepared.source.valid_until,
            applicability=prepared.source.applicability,
        )
        for score, prepared, excerpt in candidates[:limit]
    )


def retrieve(
    query: str,
    sources: list[SourceDocument],
    policy: PolicySettings,
    *,
    limit: int = 4,
    now: datetime | None = None,
) -> tuple[Evidence, ...]:
    """Backward-compatible cold retrieval wrapper for one-off queries."""
    return retrieve_prepared(
        query,
        prepare_sources(sources),
        policy,
        limit=limit,
        now=now,
    )
