from trustflow.demo import run_demo


def test_demo() -> None:
    result = run_demo()
    assert result["metrics"]["evidence_coverage"] == 1.0
    assert result["export"]["unanswerable"] == 0
    assert result["audit_events"] >= 8
