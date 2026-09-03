"""Deterministic claim-shape and evidence-applicability governance."""

from __future__ import annotations

import re
from collections.abc import Iterable

from trustflow.domain.models import ApplicabilityScope, Evidence

_SCOPE_SEPARATOR = re.compile(r"[^a-z0-9]+")
_WORD = re.compile(r"[a-z0-9][a-z0-9_-]*", re.IGNORECASE)
_NEGATION = re.compile(
    r"\b(no|not|never|cannot|can't|does not|do not|doesn't|without)\b",
    re.IGNORECASE,
)
_CONTRADICTION_SPLIT = re.compile(r"\b(?:while|whereas|but)\b", re.IGNORECASE)
_BOTH_AND = re.compile(r"\bboth\s+(.+?)\s+and\s+(.+?)(?:[?.]|$)", re.IGNORECASE)
_BROAD_PREDICATE = re.compile(
    r"^\s*(?:is|are|do|does|can|will)\b.{0,180}\b"
    r"(?:secure|safe|compliant|protected)\s*\?\s*$",
    re.IGNORECASE,
)
_UNIVERSAL_MARKERS = frozenset({"all", "always", "entire", "entirely", "every", "everywhere"})
_RISK_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "at",
        "be",
        "both",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "in",
        "is",
        "it",
        "no",
        "not",
        "of",
        "on",
        "or",
        "the",
        "to",
        "while",
        "with",
        "you",
        "your",
    }
)


def canonical_scope_value(value: str) -> str:
    """Canonicalize a scope label without maintaining a product-specific vocabulary."""
    return _SCOPE_SEPARATOR.sub("-", value.casefold()).strip("-")


def _canonical_values(values: Iterable[str]) -> frozenset[str]:
    return frozenset(normalized for value in values if (normalized := canonical_scope_value(value)))


def infer_claim_scope(question: str) -> ApplicabilityScope:
    """Extract only explicit product/region/deployment phrases from questionnaire text."""
    products: set[str] = set()
    regions: set[str] = set()
    deployments: set[str] = set()

    product_patterns = (
        re.compile(r"\b([a-z0-9][a-z0-9_-]*)\s+product\b", re.IGNORECASE),
        re.compile(
            r"\bproduct\s+(?:named|called)\s+([a-z0-9][a-z0-9_-]*)\b",
            re.IGNORECASE,
        ),
    )
    region_patterns = (
        re.compile(
            r"\b(?:in|for)\s+(?:the\s+)?([a-z0-9][a-z0-9_-]*)\s+region\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bregion\s+(?:named|called)\s+([a-z0-9][a-z0-9_-]*)\b",
            re.IGNORECASE,
        ),
    )
    deployment_patterns = (
        re.compile(
            r"\b(?:in|for)\s+([a-z0-9][a-z0-9_-]*(?:\s+[a-z0-9][a-z0-9_-]*)?)"
            r"\s+deployments?\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b([a-z0-9][a-z0-9_-]*(?:\s+[a-z0-9][a-z0-9_-]*)?)"
            r"\s+deployment\b",
            re.IGNORECASE,
        ),
    )

    for pattern in product_patterns:
        products.update(match.group(1) for match in pattern.finditer(question))
    for pattern in region_patterns:
        regions.update(match.group(1) for match in pattern.finditer(question))
    for pattern in deployment_patterns:
        deployments.update(match.group(1) for match in pattern.finditer(question))

    return ApplicabilityScope(
        products=_canonical_values(products),
        regions=_canonical_values(regions),
        deployment_models=_canonical_values(deployments),
    )


def source_matches_claim_scope(
    claim_scope: ApplicabilityScope,
    source_scope: ApplicabilityScope,
) -> bool:
    """Reject explicit mismatches; undeclared source scope remains reviewable, not trusted."""
    dimensions = (
        (claim_scope.products, source_scope.products),
        (claim_scope.regions, source_scope.regions),
        (claim_scope.deployment_models, source_scope.deployment_models),
    )
    for requested, declared in dimensions:
        normalized_requested = _canonical_values(requested)
        normalized_declared = _canonical_values(declared)
        if (
            normalized_requested
            and normalized_declared
            and not normalized_requested <= normalized_declared
        ):
            return False
    return True


def _risk_tokens(text: str) -> frozenset[str]:
    terms: set[str] = set()
    for raw in _WORD.findall(text):
        term = canonical_scope_value(raw)
        if term.startswith("encrypt"):
            term = "encrypt"
        if term and term not in _RISK_STOPWORDS:
            terms.add(term)
    return frozenset(terms)


def _applicability_unknown_reasons(
    claim_scope: ApplicabilityScope,
    evidence: tuple[Evidence, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    dimensions = (
        (
            "product",
            claim_scope.products,
            tuple(item.applicability.products for item in evidence),
        ),
        (
            "region",
            claim_scope.regions,
            tuple(item.applicability.regions for item in evidence),
        ),
        (
            "deployment_model",
            claim_scope.deployment_models,
            tuple(item.applicability.deployment_models for item in evidence),
        ),
    )
    for name, requested, declared_values in dimensions:
        if not requested:
            continue
        declared = [_canonical_values(values) for values in declared_values]
        if declared and any(not values for values in declared):
            reasons.append(f"applicability_unknown:{name}")
    return tuple(reasons)


def _partial_support_risk(question: str, evidence: tuple[Evidence, ...]) -> bool:
    match = _BOTH_AND.search(question)
    if match is None:
        return False
    facets = (_risk_tokens(match.group(1)), _risk_tokens(match.group(2)))
    if any(not facet for facet in facets):
        return True
    evidence_tokens = _risk_tokens(" ".join(item.excerpt for item in evidence))
    return any(not facet <= evidence_tokens for facet in facets)


def _overbroad_risk(question: str, evidence: tuple[Evidence, ...]) -> bool:
    question_markers = _risk_tokens(question) & _UNIVERSAL_MARKERS
    if not question_markers:
        return False
    evidence_markers = (
        _risk_tokens(" ".join(item.excerpt for item in evidence)) & _UNIVERSAL_MARKERS
    )
    return not question_markers <= evidence_markers


def _contradictory_question_risk(question: str) -> bool:
    clauses = [part.strip() for part in _CONTRADICTION_SPLIT.split(question) if part.strip()]
    if len(clauses) < 2:
        return False
    for left_index, left in enumerate(clauses):
        left_negated = _NEGATION.search(left) is not None
        left_tokens = _risk_tokens(left)
        for right in clauses[left_index + 1 :]:
            right_negated = _NEGATION.search(right) is not None
            if left_negated == right_negated:
                continue
            if len(left_tokens & _risk_tokens(right)) >= 2:
                return True
    return False


def claim_risk_reasons(question: str, evidence: tuple[Evidence, ...]) -> tuple[str, ...]:
    """Return conservative reasons why relevant evidence must not become an automatic claim."""
    reasons: list[str] = list(_applicability_unknown_reasons(infer_claim_scope(question), evidence))
    if _partial_support_risk(question, evidence):
        reasons.append("partial_support_risk")
    if _overbroad_risk(question, evidence):
        reasons.append("overbroad_claim_risk")
    if _BROAD_PREDICATE.match(question):
        reasons.append("ambiguous_claim_risk")
    if _contradictory_question_risk(question):
        reasons.append("contradictory_claim_risk")
    return tuple(dict.fromkeys(reasons))
