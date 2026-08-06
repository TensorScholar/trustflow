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


def test_unapproved_source_excluded() -> None:
    assert (
        retrieve(
            "encryption",
            [source("x", "encryption", approved=False)],
            PolicySettings(),
        )
        == ()
    )


def test_old_source_excluded() -> None:
    assert (
        retrieve(
            "encryption",
            [source("x", "encryption", updated_at=datetime.now(UTC) - timedelta(days=500))],
            PolicySettings(maximum_source_age_days=30),
        )
        == ()
    )
