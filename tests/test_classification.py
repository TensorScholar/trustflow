import pytest

from trustflow.domain.classification import classify_sensitivity
from trustflow.domain.models import QuestionSensitivity


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("How do you comply with GDPR?", QuestionSensitivity.PRIVACY),
        ("What are your indemnity terms?", QuestionSensitivity.LEGAL),
        ("Do you have SOC 2?", QuestionSensitivity.SECURITY),
        ("Provide financial insurance details?", QuestionSensitivity.FINANCIAL),
        ("Where are you hosted?", QuestionSensitivity.STANDARD),
    ],
)
def test_classification(text, expected) -> None:
    assert classify_sensitivity(text) is expected
