"""Synthetic retrieval performance probe.

This probe is an engineering measurement harness, not a production benchmark or SLO.
It intentionally exercises the public cold ``retrieve`` path on a fixed deterministic corpus.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from time import perf_counter

from trustflow.domain.models import PolicySettings, SourceDocument
from trustflow.domain.retrieval import retrieve

SOURCE_COUNT = 48
PASSAGES_PER_SOURCE = 24
QUESTION_COUNT = 160
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


def main() -> None:
    policy = PolicySettings()
    sources = _sources()
    questions = _questions()

    started = perf_counter()
    records: list[tuple[str, tuple[tuple[str, float, str], ...]]] = []
    for question in questions:
        evidence = retrieve(question, sources, policy, now=FIXED_TIME)
        records.append(
            (
                question,
                tuple((item.source_id, item.score, item.excerpt) for item in evidence),
            )
        )
    elapsed = perf_counter() - started

    checksum = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload = {
        "evidence_category": "synthetically_observed",
        "measurement": "cold_retrieval_baseline",
        "source_count": SOURCE_COUNT,
        "passages_per_source": PASSAGES_PER_SOURCE,
        "question_count": QUESTION_COUNT,
        "retrieval_calls": len(questions),
        "elapsed_seconds": round(elapsed, 6),
        "result_checksum": checksum,
        "production_slo_claim": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
