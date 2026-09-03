"""Synthetic retrieval performance probe.

This probe is an engineering measurement harness, not a production benchmark or SLO.
It compares the backward-compatible cold path with a prepared multi-query source snapshot in the
same process and requires their semantic result checksums to remain identical.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from statistics import median
from time import perf_counter
from typing import Callable

from trustflow.domain.models import Evidence, PolicySettings, SourceDocument
from trustflow.domain.retrieval import prepare_sources, retrieve, retrieve_prepared

SOURCE_COUNT = 48
PASSAGES_PER_SOURCE = 24
QUESTION_COUNT = 160
REPETITIONS = 3
MINIMUM_SAME_PROCESS_SPEEDUP = 2.0
FIXED_TIME = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _sources() -> list[SourceDocument]:
    sources: list[SourceDocument] = []
    for source_index in range(SOURCE_COUNT):
        passages = []
        for passage_index in range(PASSAGES_PER_SOURCE):
            control = (source_index + passage_index) % 16
            passages.append(
                "Control "
                f"{control} protects customer data with encryption, access review, logging, "
                f"retention, backup, region-{source_index % 4}, and deployment-{source_index % 3}."
            )
        sources.append(
            SourceDocument(
                id=f"source-{source_index:03d}",
                title=f"Synthetic policy {source_index:03d}",
                owner="performance-probe",
                version="1",
                content="\n".join(passages),
                source_uri=f"synthetic://performance/source-{source_index:03d}",
                approved=True,
                updated_at=FIXED_TIME,
            )
        )
    return sources


def _questions() -> list[str]:
    return [
        "How does control "
        f"{index % 16} protect customer data with encryption and access review?"
        for index in range(QUESTION_COUNT)
    ]


def _checksum(records: list[tuple[str, tuple[tuple[str, float, str], ...]]]) -> str:
    return hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _run(
    questions: list[str],
    lookup: Callable[[str], tuple[Evidence, ...]],
) -> tuple[float, str]:
    started = perf_counter()
    records: list[tuple[str, tuple[tuple[str, float, str], ...]]] = []
    for question in questions:
        evidence = lookup(question)
        records.append(
            (
                question,
                tuple((item.source_id, item.score, item.excerpt) for item in evidence),
            )
        )
    return perf_counter() - started, _checksum(records)


def main() -> None:
    policy = PolicySettings()
    sources = _sources()
    questions = _questions()

    cold_times: list[float] = []
    prepared_times: list[float] = []
    cold_checksum = ""
    prepared_checksum = ""
    for _ in range(REPETITIONS):
        cold_elapsed, cold_checksum = _run(
            questions,
            lambda question: retrieve(question, sources, policy, now=FIXED_TIME),
        )
        prepared_started = perf_counter()
        prepared_sources = prepare_sources(sources)
        prepared_build_seconds = perf_counter() - prepared_started
        prepared_elapsed, prepared_checksum = _run(
            questions,
            lambda question: retrieve_prepared(
                question,
                prepared_sources,
                policy,
                now=FIXED_TIME,
            ),
        )
        cold_times.append(cold_elapsed)
        prepared_times.append(prepared_build_seconds + prepared_elapsed)

    if cold_checksum != prepared_checksum:
        raise SystemExit("prepared retrieval changed deterministic result checksum")

    cold_median = median(cold_times)
    prepared_median = median(prepared_times)
    speedup = cold_median / prepared_median if prepared_median else float("inf")
    payload = {
        "evidence_category": "synthetically_observed",
        "measurement": "cold_vs_prepared_retrieval",
        "source_count": SOURCE_COUNT,
        "passages_per_source": PASSAGES_PER_SOURCE,
        "question_count": QUESTION_COUNT,
        "retrieval_calls_per_repetition": len(questions),
        "repetitions": REPETITIONS,
        "cold_median_seconds": round(cold_median, 6),
        "prepared_median_seconds_including_build": round(prepared_median, 6),
        "same_process_speedup": round(speedup, 3),
        "minimum_same_process_speedup": MINIMUM_SAME_PROCESS_SPEEDUP,
        "result_checksum": cold_checksum,
        "semantic_equivalence": True,
        "production_slo_claim": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if speedup < MINIMUM_SAME_PROCESS_SPEEDUP:
        raise SystemExit(
            "prepared retrieval fell below the conservative same-process performance guardrail"
        )


if __name__ == "__main__":
    main()
