import pytest

from trustflow.application.evaluation import evaluate_adversarial_cases
from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.models import (
    AnswerStatus,
    DocumentFormat,
    EvaluationCase,
    EvaluationScenario,
    Question,
    QuestionLocation,
    QuestionSensitivity,
)
from trustflow.evaluation import load_adversarial_corpus, run_adversarial_corpus


def _question(identifier: str, text: str) -> Question:
    return Question(
        id=identifier,
        text=text,
        location=QuestionLocation(format=DocumentFormat.JSON, key=identifier),
    )


def test_legacy_evaluation_contract_remains_compatible(service) -> None:
    summary = service.evaluate_cases(
        [
            EvaluationCase(
                id="x",
                question=Question(
                    id="q",
                    text="Do you encrypt customer data at rest?",
                    sensitivity=QuestionSensitivity.SECURITY,
                    location=QuestionLocation(format=DocumentFormat.JSON, key="0"),
                ),
                expected_status=AnswerStatus.REVIEW_REQUIRED,
                expected_source_ids=frozenset({"security"}),
            )
        ]
    )
    assert summary.status_accuracy == 1
    assert summary.citation_recall == 1
    assert summary.unsupported_answer_rate == 0
    assert summary.sensitive_auto_approval_rate == 0


def test_adversarial_evaluation_exposes_false_acceptance_and_bad_citation(service) -> None:
    cases = [
        EvaluationCase(
            id="supported",
            scenario=EvaluationScenario.SUPPORTED,
            question=_question("supported", "Do you encrypt customer data at rest?"),
            expected_status=AnswerStatus.ANSWERED,
            expected_source_ids=frozenset({"security"}),
            candidate_source_ids=frozenset({"security"}),
            allow_auto_answer=True,
        ),
        EvaluationCase(
            id="wrong-scope",
            scenario=EvaluationScenario.WRONG_PRODUCT_SCOPE,
            question=_question("wrong-scope", "Do you encrypt customer data at rest?"),
            expected_status=AnswerStatus.UNANSWERABLE,
            forbidden_source_ids=frozenset({"security"}),
            candidate_source_ids=frozenset({"security"}),
            allow_auto_answer=False,
        ),
    ]
    summary = evaluate_adversarial_cases(
        cases=cases,
        sources=service.store.list_sources(),
        generator=service.generator,
        policy=service.policy,
    )

    assert summary.cases == 2
    assert summary.status_accuracy == 0.5
    assert summary.citation_recall == 1.0
    assert summary.citation_precision == 0.5
    assert summary.false_acceptance_rate == 1.0
    assert summary.auto_answer_precision == 0.5
    assert summary.forbidden_citation_rate == 1.0
    assert summary.failed_case_ids == ("wrong-scope",)
    assert summary.scenario_failures == {"wrong_product_scope": 1}


def test_adversarial_evaluation_rejects_unknown_candidate_sources(service) -> None:
    case = EvaluationCase(
        id="missing-source",
        scenario=EvaluationScenario.NO_EVIDENCE,
        question=_question("missing-source", "Is there evidence?"),
        expected_status=AnswerStatus.UNANSWERABLE,
        candidate_source_ids=frozenset({"does-not-exist"}),
    )
    with pytest.raises(InvalidTransitionError, match="missing candidate sources"):
        evaluate_adversarial_cases(
            cases=[case],
            sources=service.store.list_sources(),
            generator=service.generator,
            policy=service.policy,
        )


def test_adversarial_corpus_covers_required_scenarios_reproducibly(service) -> None:
    corpus = load_adversarial_corpus()
    covered = {case.scenario for case in corpus.draft_cases}
    covered.update(case.scenario for case in corpus.revalidation_cases)
    assert covered == set(EvaluationScenario)
    assert len(corpus.draft_cases) == 15
    assert len(corpus.revalidation_cases) == 1

    duplicate = next(
        case for case in corpus.draft_cases if case.scenario is EvaluationScenario.DUPLICATE_QUESTION
    )
    original = next(case for case in corpus.draft_cases if case.id == duplicate.duplicate_of)
    assert duplicate.question == original.question

    report = run_adversarial_corpus(generator=service.generator)
    assert report.evidence_category == "synthetically_observed"
    assert report.total_cases == 16
    assert report.draft.cases == 15
    assert report.revalidation_cases == 1
    assert report.revalidation_failures == ()
    for value in (
        report.draft.status_accuracy,
        report.draft.citation_recall,
        report.draft.citation_precision,
        report.draft.false_acceptance_rate,
        report.draft.auto_answer_precision,
        report.draft.forbidden_citation_rate,
    ):
        assert 0.0 <= value <= 1.0
