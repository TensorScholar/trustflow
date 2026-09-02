"""Deterministic adversarial claim evaluation."""

from __future__ import annotations

from collections import Counter

from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.models import (
    AnswerStatus,
    EvaluationCase,
    EvaluationSummary,
    PolicySettings,
    SourceDocument,
)
from trustflow.domain.policy import decide_status
from trustflow.domain.retrieval import retrieve
from trustflow.ports.interfaces import AnswerGenerator


def evaluate_adversarial_cases(
    *,
    cases: list[EvaluationCase],
    sources: list[SourceDocument],
    generator: AnswerGenerator,
    policy: PolicySettings,
) -> EvaluationSummary:
    """Evaluate claim safety with false acceptance weighted ahead of generation quality."""
    source_by_id = {source.id: source for source in sources}
    status_hits = 0
    citation_hits = 0
    citation_expected_total = 0
    citation_predicted_total = 0
    false_acceptances = 0
    auto_answers = 0
    safe_auto_answers = 0
    non_auto_cases = 0
    forbidden_cases = 0
    forbidden_hits = 0
    unsupported = 0
    sensitive_cases = 0
    sensitive_auto = 0
    failed_case_ids: list[str] = []
    scenario_failures: Counter[str] = Counter()

    for case in cases:
        if case.candidate_source_ids is None:
            candidate_sources = list(sources)
        else:
            missing = case.candidate_source_ids - source_by_id.keys()
            if missing:
                raise InvalidTransitionError(
                    f"evaluation case {case.id} references missing candidate sources: "
                    + ", ".join(sorted(missing))
                )
            candidate_sources = [
                source for source in sources if source.id in case.candidate_source_ids
            ]

        evidence = retrieve(
            case.question.text,
            candidate_sources,
            policy,
            now=case.evaluated_at,
        )
        text, confidence = generator.generate(
            question=case.question.text,
            evidence=evidence,
        )
        status, _ = decide_status(
            confidence=confidence,
            evidence=evidence,
            sensitivity=case.question.sensitivity,
            policy=policy,
            now=case.evaluated_at,
        )

        actual_source_ids = {item.source_id for item in evidence}
        expected_hits = actual_source_ids & case.expected_source_ids
        forbidden = actual_source_ids & case.forbidden_source_ids

        status_ok = status is case.expected_status
        expected_sources_ok = case.expected_source_ids <= actual_source_ids
        forbidden_ok = not forbidden
        auto_answer_ok = status is not AnswerStatus.ANSWERED or case.allow_auto_answer
        case_ok = status_ok and expected_sources_ok and forbidden_ok and auto_answer_ok

        status_hits += status_ok
        citation_hits += len(expected_hits)
        citation_expected_total += len(case.expected_source_ids)
        citation_predicted_total += len(actual_source_ids)

        if case.allow_auto_answer:
            if status is AnswerStatus.ANSWERED:
                safe_auto_answers += 1
        else:
            non_auto_cases += 1
            if status is AnswerStatus.ANSWERED:
                false_acceptances += 1

        if status is AnswerStatus.ANSWERED:
            auto_answers += 1

        if case.forbidden_source_ids:
            forbidden_cases += 1
            forbidden_hits += bool(forbidden)

        unsupported += bool(text and not evidence and status is AnswerStatus.ANSWERED)
        if case.question.sensitivity.value != "standard":
            sensitive_cases += 1
            sensitive_auto += status is AnswerStatus.ANSWERED

        if not case_ok:
            failed_case_ids.append(case.id)
            scenario_failures[case.scenario.value] += 1

    total = len(cases)
    return EvaluationSummary(
        cases=total,
        status_accuracy=status_hits / total if total else 1.0,
        citation_recall=(
            citation_hits / citation_expected_total if citation_expected_total else 1.0
        ),
        citation_precision=(
            citation_hits / citation_predicted_total if citation_predicted_total else 1.0
        ),
        false_acceptance_rate=(
            false_acceptances / non_auto_cases if non_auto_cases else 0.0
        ),
        auto_answer_precision=(safe_auto_answers / auto_answers if auto_answers else 1.0),
        forbidden_citation_rate=(forbidden_hits / forbidden_cases if forbidden_cases else 0.0),
        unsupported_answer_rate=unsupported / total if total else 0.0,
        sensitive_auto_approval_rate=(
            sensitive_auto / sensitive_cases if sensitive_cases else 0.0
        ),
        failed_case_ids=tuple(failed_case_ids),
        scenario_failures=dict(sorted(scenario_failures.items())),
    )
