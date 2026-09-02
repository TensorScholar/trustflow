from datetime import UTC, datetime, timedelta

from trustflow.domain.models import PolicySettings, SourceDocument
from trustflow.domain.retrieval import retrieve


def source(identifier: str, content: str, **kwargs) -> SourceDocument:
    return SourceDocument(
        id=identifier,
        title=identifier,
        owner="o",
        version="1",
        content=content,
        source_uri=f"policy://{identifier}",
        **kwargs,
    )


def test_retrieve_matching_source() -> None:
    results = retrieve(
        "Do you encrypt customer data at rest?",
        [source("security", "Customer data is encrypted at rest with AES-256.")],
        PolicySettings(),
    )
    assert results[0].source_id == "security"
    assert len(results[0].source_digest) == 64


def test_retrieve_selects_matching_passage_not_first_line() -> None:
    results = retrieve(
        "Do you encrypt customer data at rest?",
        [
            source(
                "security",
                "Company overview is public.\nCustomer data is encrypted at rest with AES-256.",
            )
        ],
        PolicySettings(),
    )
    assert results[0].excerpt == "Customer data is encrypted at rest with AES-256."


def test_unapproved_source_excluded() -> None:
    assert (
        retrieve(
            "encryption",
            [source("x", "encryption", approved=False)],
            PolicySettings(),
        )
        == ()
    )


def test_old_source_is_returned_for_explicit_stale_policy_gate() -> None:
    results = retrieve(
        "encryption",
        [source("x", "encryption", updated_at=datetime.now(UTC) - timedelta(days=500))],
        PolicySettings(maximum_source_age_days=30),
    )
    assert results[0].source_id == "x"
