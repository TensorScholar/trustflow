"""Reproducible adversarial evaluation corpus loading and execution."""

from __future__ import annotations

from importlib.resources import files
from typing import Literal

from pydantic import AwareDatetime

from trustflow.application.evaluation import evaluate_adversarial_cases
from trustflow.domain.evidence import evidence_invalidation_reason
from trustflow.domain.models import (
    AnswerStatus,
    DocumentFormat,
    EvaluationCase,
    EvaluationScenario,
    EvaluationSummary,
    PolicySettings,
    Question,
    QuestionLocation,
    QuestionSensitivity,
    SourceDocument,
    StrictModel,
)
from trustflow.domain.retrieval import retrieve
from trustflow.ports.interfaces import AnswerGenerator


class DraftCaseSpec(StrictModel):
    id: str
    scenario: EvaluationScenario
    question: str
    sensitivity: QuestionSensitivity = QuestionSensitivity.STANDARD
    expected_status: AnswerStatus
    expected_source_ids: frozenset[str] = frozenset()
    forbidden_source_ids: frozenset[str] = frozenset()
    candidate_source_ids: frozenset[str] | None = None
    allow_auto_answer: bool = False
    duplicate_of: str | None = None


class RevalidationCaseSpec(StrictModel):
    id: str
    scenario: EvaluationScenario
    question: str
    expected_reason: str
    snapshot_source: SourceDocument
    current_source: SourceDocument


class AdversarialCorpus(StrictModel):
    evaluated_at: AwareDatetime
    sources: tuple[SourceDocument, ...]
    draft_cases: tuple[DraftCaseSpec, ...]
    revalidation_cases: tuple[RevalidationCaseSpec, ...]


class AdversarialEvaluationReport(StrictModel):
    evidence_category: Literal["synthetically_observed"] = "synthetically_observed"
    evaluated_at: AwareDatetime
    total_cases: int
    draft: EvaluationSummary
    revalidation_cases: int
    revalidation_failures: tuple[str, ...] = ()
    failed_case_ids: tuple[str, ...] = ()


def load_adversarial_corpus() -> AdversarialCorpus:
    resource = files("trustflow").joinpath("data/adversarial_claim_corpus.json")
    corpus = AdversarialCorpus.model_validate_json(resource.read_text(encoding="utf-8"))

    covered = {case.scenario for case in corpus.draft_cases}
    covered.update(case.scenario for case in corpus.revalidation_cases)
    required = set(EvaluationScenario)
    if covered != required:
        missing = sorted(item.value for item in required - covered)
        unexpected = sorted(item.value for item in covered - required)
        raise ValueError(
            f"adversarial corpus scenario coverage mismatch; missing={missing}, unexpected={unexpected}"
        )

    draft_by_id = {case.id: case for case in corpus.draft_cases}
    if len(draft_by_id) != len(corpus.draft_cases):
        raise ValueError("adversarial corpus contains duplicate case ids")
    for case in corpus.draft_cases:
        if case.duplicate_of is None:
            continue
        original = draft_by_id.get(case.duplicate_of)
        if original is None:
            raise ValueError(f"duplicate case {case.id} references missing case {case.duplicate_of}")
        if original.question != case.question:
            raise ValueError(f"duplicate case {case.id} does not preserve the original question text")

    return corpus


def materialize_draft_cases(corpus: AdversarialCorpus) -> list[EvaluationCase]:
    return [
        EvaluationCase(
            id=spec.id,
            scenario=spec.scenario,
            question=Question(
                id=spec.id,
                text=spec.question,
                sensitivity=spec.sensitivity,
                location=QuestionLocation(format=DocumentFormat.JSON, key=spec.id),
            ),
            expected_status=spec.expected_status,
            expected_source_ids=spec.expected_source_ids,
            forbidden_source_ids=spec.forbidden_source_ids,
            candidate_source_ids=spec.candidate_source_ids,
            allow_auto_answer=spec.allow_auto_answer,
            evaluated_at=corpus.evaluated_at,
        )
        for spec in corpus.draft_cases
    ]


def _evaluate_revalidation_cases(
    corpus: AdversarialCorpus,
    policy: PolicySettings,
) -> tuple[str, ...]:
    failures: list[str] = []
    for case in corpus.revalidation_cases:
        snapshot = retrieve(
            case.question,
            [case.snapshot_source],
            policy,
            limit=1,
            now=corpus.evaluated_at,
        )
        if len(snapshot) != 1:
            failures.append(case.id)
            continue
        reason = evidence_invalidation_reason(
            case.current_source,
            snapshot[0],
            policy,
            now=corpus.evaluated_at,
        )
        if reason != case.expected_reason:
            failures.append(case.id)
    return tuple(failures)


def run_adversarial_corpus(
    *,
    generator: AnswerGenerator,
    policy: PolicySettings | None = None,
) -> AdversarialEvaluationReport:
    corpus = load_adversarial_corpus()
    active_policy = policy or PolicySettings()
    draft_summary = evaluate_adversarial_cases(
        cases=materialize_draft_cases(corpus),
        sources=list(corpus.sources),
        generator=generator,
        policy=active_policy,
    )
    revalidation_failures = _evaluate_revalidation_cases(corpus, active_policy)
    failed_case_ids = tuple(
        dict.fromkeys((*draft_summary.failed_case_ids, *revalidation_failures))
    )
    return AdversarialEvaluationReport(
        evaluated_at=corpus.evaluated_at,
        total_cases=len(corpus.draft_cases) + len(corpus.revalidation_cases),
        draft=draft_summary,
        revalidation_cases=len(corpus.revalidation_cases),
        revalidation_failures=revalidation_failures,
        failed_case_ids=failed_case_ids,
    )
