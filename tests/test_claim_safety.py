from datetime import UTC, datetime

from trustflow.domain.claim_safety import (
    claim_risk_reasons,
    infer_claim_scope,
    source_matches_claim_scope,
)
from trustflow.domain.evidence import evidence_invalidation_reason, source_provenance_digest
from trustflow.domain.models import ApplicabilityScope, PolicySettings, SourceDocument
from trustflow.domain.retrieval import retrieve


def _source(scope: ApplicabilityScope) -> SourceDocument:
    return SourceDocument(
        id="scoped",
        title="Scoped security statement",
        owner="security",
        version="1",
        content="Cloud product customer data in the EU region is encrypted at rest.",
        source_uri="evidence://scoped/v1",
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
        applicability=scope,
    )


def test_claim_scope_extraction_is_dimension_specific_and_canonical() -> None:
    product = infer_claim_scope("Does the OnPrem product encrypt customer data at rest?")
    region = infer_claim_scope("Is customer data in the US region encrypted at rest?")
    deployment = infer_claim_scope(
        "Is customer data encrypted at rest in customer-managed deployments?"
    )

    assert product.products == frozenset({"onprem"})
    assert region.regions == frozenset({"us"})
    assert deployment.deployment_models == frozenset({"customer-managed"})


def test_scope_parser_underextracts_ambiguous_structural_wording() -> None:
    scope = infer_claim_scope("Does the product encrypt customer data in the region?")
    assert scope.products == frozenset()
    assert scope.regions == frozenset()


def test_explicit_mismatch_fails_but_undeclared_scope_is_not_treated_as_global() -> None:
    requested = ApplicabilityScope(products=frozenset({"onprem"}))
    cloud = ApplicabilityScope(products=frozenset({"cloud"}))

    assert not source_matches_claim_scope(requested, cloud)
    assert source_matches_claim_scope(requested, ApplicabilityScope())


def test_multiple_requested_scope_values_require_complete_declared_coverage() -> None:
    requested = ApplicabilityScope(products=frozenset({"cloud", "onprem"}))
    cloud_only = ApplicabilityScope(products=frozenset({"cloud"}))
    both = ApplicabilityScope(products=frozenset({"cloud", "onprem"}))

    assert not source_matches_claim_scope(requested, cloud_only)
    assert source_matches_claim_scope(requested, both)


def test_any_unresolved_citation_scope_requires_review() -> None:
    question = "Does the cloud product encrypt customer data at rest?"
    scoped = _source(ApplicabilityScope(products=frozenset({"cloud"})))
    unscoped = _source(ApplicabilityScope()).model_copy(
        update={"id": "unscoped", "source_uri": "evidence://unscoped/v1"}
    )
    evidence = retrieve(question, [scoped, unscoped], PolicySettings())

    assert len(evidence) == 2
    assert "applicability_unknown:product" in claim_risk_reasons(question, evidence)


def test_applicability_is_canonicalized_before_provenance_hashing() -> None:
    first = _source(
        ApplicabilityScope(
            products=frozenset({"cloud", "enterprise"}),
            regions=frozenset({"eu", "us"}),
        )
    )
    second = _source(
        ApplicabilityScope(
            products=frozenset({"enterprise", "cloud"}),
            regions=frozenset({"us", "eu"}),
        )
    )
    assert source_provenance_digest(first) == source_provenance_digest(second)


def test_applicability_drift_invalidates_existing_evidence_snapshot() -> None:
    source = _source(ApplicabilityScope(products=frozenset({"cloud"})))
    evidence = retrieve(
        "Does the cloud product encrypt customer data at rest?",
        [source],
        PolicySettings(),
    )[0]
    changed = source.model_copy(
        update={"applicability": ApplicabilityScope(products=frozenset({"onprem"}))}
    )

    reason = evidence_invalidation_reason(
        changed,
        evidence,
        PolicySettings(maximum_source_age_days=1000),
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )
    assert reason == "source_provenance_changed"
