import json
from datetime import UTC, datetime

from trustflow.adapters.exporters import ExporterRegistry
from trustflow.adapters.parsers import ParserRegistry
from trustflow.domain.models import (
    AnswerStatus,
    ApplicabilityScope,
    DraftAnswer,
    Evidence,
)


def test_json_export_preserves_evidence_applicability_lineage(tmp_path) -> None:
    source = tmp_path / "q.json"
    source.write_text('{"questions":["Question?"]}', encoding="utf-8")
    questionnaire = ParserRegistry().parse(source)
    evidence = Evidence(
        source_id="security",
        source_title="Scoped security evidence",
        source_uri="evidence://security/v1",
        source_version="1",
        source_digest="a" * 64,
        owner="security",
        excerpt="Cloud EU customer data is encrypted at rest.",
        score=1,
        updated_at=datetime.now(UTC),
        applicability=ApplicabilityScope(
            products=frozenset({"cloud"}),
            regions=frozenset({"eu"}),
            deployment_models=frozenset({"managed-saas"}),
        ),
    )
    answer = DraftAnswer(
        questionnaire_id=questionnaire.id,
        question_id="q1",
        text=evidence.excerpt,
        status=AnswerStatus.ANSWERED,
        confidence=1,
        evidence=(evidence,),
    )
    output = tmp_path / "out.json"

    ExporterRegistry().export(questionnaire, [answer], {}, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload[0]["sources"][0]["applicability"] == {
        "deployment_models": ["managed-saas"],
        "products": ["cloud"],
        "regions": ["eu"],
    }
