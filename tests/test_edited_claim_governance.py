import json
from datetime import UTC, datetime

import pytest

from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.models import ReviewState, SourceDocument


def _questionnaire(tmp_path):
    path = tmp_path / "questionnaire.json"
    path.write_text(
        json.dumps({"questions": ["Do you encrypt customer data at rest?"]}),
        encoding="utf-8",
    )
    return path


def test_arbitrary_human_edit_cannot_expand_evidence_governance(service, tmp_path) -> None:
    questionnaire = service.import_questionnaire(_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]

    with pytest.raises(InvalidTransitionError, match="edited_text_not_evidence_bound"):
        service.review(
            answer.id,
            reviewer="security",
            state=ReviewState.EDITED,
            final_text="We encrypt all customer data everywhere and are fully compliant.",
        )


def test_edited_review_may_select_a_complete_retained_evidence_excerpt(service, tmp_path) -> None:
    service.ingest_source(
        SourceDocument(
            id="security-alternative",
            title="Security implementation note",
            owner="security",
            version="1",
            content="Customer data is encrypted at rest using AES-256.",
            source_uri="policy://security/implementation",
            updated_at=datetime.now(UTC),
            tags=frozenset({"encrypt", "customer", "data", "rest", "aes-256"}),
        )
    )
    questionnaire = service.import_questionnaire(_questionnaire(tmp_path))
    answer = service.draft(questionnaire.id)[0]
    alternative = next(
        item.excerpt
        for item in answer.evidence
        if item.excerpt.casefold() != answer.text.casefold()
    )

    review = service.review(
        answer.id,
        reviewer="security",
        state=ReviewState.EDITED,
        final_text=alternative,
    )
    assert review.final_text == alternative
    service.export(questionnaire.id, tmp_path / "edited.json")
    assert service.governance_metrics(questionnaire.id)["reviewer_edit_rate"] == 1.0
