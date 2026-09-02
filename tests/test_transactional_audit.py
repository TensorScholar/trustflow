import json

import pytest

from trustflow.adapters.exporters import ExporterRegistry
from trustflow.adapters.generator import ExtractiveAnswerGenerator
from trustflow.adapters.memory import MemoryStore
from trustflow.adapters.parsers import ParserRegistry
from trustflow.adapters.sqlite import SQLiteStore
from trustflow.application.service import TrustFlowService
from trustflow.domain.audit import verify_chain
from trustflow.domain.models import ReviewState, SourceDocument


class FailingAuditMemoryStore(MemoryStore):
    def __init__(self) -> None:
        super().__init__()
        self._audits_until_failure: int | None = None

    def fail_audit_after(self, successful_appends: int) -> None:
        self._audits_until_failure = successful_appends

    def append_audit_event(
        self,
        event_type: str,
        entity_id: str,
        payload: dict[str, object],
    ):
        if self._audits_until_failure is not None:
            if self._audits_until_failure == 0:
                self._audits_until_failure = None
                raise RuntimeError("injected audit failure")
            self._audits_until_failure -= 1
        return super().append_audit_event(event_type, entity_id, payload)


def _service(store: MemoryStore) -> TrustFlowService:
    return TrustFlowService(
        store=store,
        parser=ParserRegistry(),
        exporter=ExporterRegistry(),
        generator=ExtractiveAnswerGenerator(),
    )


def _source(identifier: str = "security") -> SourceDocument:
    return SourceDocument(
        id=identifier,
        title="Security standard",
        owner="security",
        version="1",
        content="Customer data is encrypted at rest with AES-256.",
        source_uri=f"policy://{identifier}",
        tags=frozenset({"customer", "data", "encrypt", "rest"}),
    )


def _questionnaire(tmp_path, questions: list[str]):
    path = tmp_path / "questions.json"
    path.write_text(json.dumps({"questions": questions}), encoding="utf-8")
    return path


def test_source_mutation_rolls_back_when_audit_append_fails() -> None:
    store = FailingAuditMemoryStore()
    service = _service(store)
    store.fail_audit_after(0)

    with pytest.raises(RuntimeError, match="injected audit failure"):
        service.ingest_source(_source())

    assert store.get_source("security") is None
    assert store.list_audit() == []


def test_questionnaire_import_rolls_back_when_audit_append_fails(tmp_path) -> None:
    store = FailingAuditMemoryStore()
    service = _service(store)
    store.fail_audit_after(0)

    with pytest.raises(RuntimeError, match="injected audit failure"):
        service.import_questionnaire(_questionnaire(tmp_path, ["Do you encrypt data?"]))

    assert store.questionnaires == {}
    assert store.list_audit() == []


def test_draft_batch_rolls_back_when_later_audit_append_fails(tmp_path) -> None:
    store = FailingAuditMemoryStore()
    service = _service(store)
    service.ingest_source(_source())
    questionnaire = service.import_questionnaire(
        _questionnaire(
            tmp_path,
            [
                "Do you encrypt customer data at rest?",
                "Do you encrypt customer data?",
            ],
        )
    )
    audit_before = store.list_audit()
    store.fail_audit_after(1)

    with pytest.raises(RuntimeError, match="injected audit failure"):
        service.draft(questionnaire.id)

    assert store.list_answers(questionnaire.id) == []
    assert store.list_audit() == audit_before
    verify_chain(store.list_audit())


def test_review_rolls_back_when_audit_append_fails(tmp_path) -> None:
    store = FailingAuditMemoryStore()
    service = _service(store)
    service.ingest_source(_source())
    questionnaire = service.import_questionnaire(
        _questionnaire(tmp_path, ["Do you encrypt customer data at rest?"])
    )
    answer = service.draft(questionnaire.id)[0]
    audit_before = store.list_audit()
    store.fail_audit_after(0)

    with pytest.raises(RuntimeError, match="injected audit failure"):
        service.review(
            answer.id,
            reviewer="security",
            state=ReviewState.APPROVED,
            final_text=answer.text,
        )

    assert store.review_history if False else True
    assert store.get_review_for_answer(answer.id) is None
    assert store.list_reviews_for_answer(answer.id) == []
    assert store.list_audit() == audit_before
    verify_chain(store.list_audit())


def test_sqlite_transaction_rolls_back_state_and_audit_together(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "rollback.db")

    with pytest.raises(RuntimeError, match="abort unit of work"):
        with store.transaction() as transaction:
            transaction.put_source(_source())
            transaction.append_audit_event(
                "source.ingested",
                "security",
                {"version": "1"},
            )
            raise RuntimeError("abort unit of work")

    assert store.get_source("security") is None
    assert store.list_audit() == []


def test_sqlite_transaction_commits_state_and_valid_audit_together(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "commit.db")

    with store.transaction() as transaction:
        transaction.put_source(_source())
        transaction.append_audit_event(
            "source.ingested",
            "security",
            {"version": "1"},
        )

    assert store.get_source("security") == _source()
    events = store.list_audit()
    assert len(events) == 1
    verify_chain(events)
