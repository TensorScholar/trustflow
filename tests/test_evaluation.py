from trustflow.domain.models import (
    AnswerStatus,
    DocumentFormat,
    EvaluationCase,
    Question,
    QuestionLocation,
    QuestionSensitivity,
)


def test_evaluation(service) -> None:
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
