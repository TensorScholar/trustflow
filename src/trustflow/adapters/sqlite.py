from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from trustflow.domain.audit import make_event
from trustflow.domain.errors import InvalidTransitionError
from trustflow.domain.models import (
    AuditEvent,
    DraftAnswer,
    Questionnaire,
    ReviewDecision,
    SourceDocument,
)

T = TypeVar("T", bound=BaseModel)


class _SQLiteTransaction:
    """Single-connection unit of work for governed state plus audit writes."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def _put(self, kind: str, identifier: str, model: BaseModel) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO objects(kind,id,payload) VALUES(?,?,?)",
            (kind, identifier, model.model_dump_json()),
        )

    def put_source(self, source: SourceDocument) -> None:
        self._put("source", source.id, source)

    def put_questionnaire(self, questionnaire: Questionnaire) -> None:
        self._put("questionnaire", questionnaire.id, questionnaire)

    def put_answer(self, answer: DraftAnswer) -> None:
        self._put("answer", answer.id, answer)

    def put_review(self, review: ReviewDecision) -> None:
        try:
            self.connection.execute(
                "INSERT INTO review_decisions(id,answer_id,payload) VALUES(?,?,?)",
                (review.id, review.answer_id, review.model_dump_json()),
            )
        except sqlite3.IntegrityError as exc:
            raise InvalidTransitionError(f"review decision already exists: {review.id}") from exc

    def append_audit_event(
        self,
        event_type: str,
        entity_id: str,
        payload: dict[str, object],
    ) -> AuditEvent:
        row = self.connection.execute(
            "SELECT payload FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_event = AuditEvent.model_validate_json(row[0]) if row else None
        event = make_event(
            sequence=(previous_event.sequence + 1 if previous_event else 1),
            event_type=event_type,
            entity_id=entity_id,
            payload=payload,
            previous_hash=(previous_event.event_hash if previous_event else "0" * 64),
        )
        self.connection.execute(
            "INSERT INTO audit_events(sequence,payload) VALUES(?,?)",
            (event.sequence, event.model_dump_json()),
        )
        return event


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS objects (
                    kind TEXT NOT NULL,
                    id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (kind,id)
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    answer_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_decisions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    answer_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_review_decisions_answer_sequence
                    ON review_decisions(answer_id, sequence);
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                """
            )
            legacy_rows = connection.execute("SELECT payload FROM reviews").fetchall()
            for (payload,) in legacy_rows:
                review = ReviewDecision.model_validate_json(payload)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO review_decisions(id,answer_id,payload)
                    VALUES(?,?,?)
                    """,
                    (review.id, review.answer_id, review.model_dump_json()),
                )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA synchronous=NORMAL")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[_SQLiteTransaction]:
        """Atomically commit governed state mutations and their audit events."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            yield _SQLiteTransaction(connection)

    def _put(self, kind: str, identifier: str, model: BaseModel) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO objects(kind,id,payload) VALUES(?,?,?)",
                (kind, identifier, model.model_dump_json()),
            )

    def _get(self, kind: str, identifier: str, model: type[T]) -> T | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM objects WHERE kind=? AND id=?", (kind, identifier)
            ).fetchone()
        return model.model_validate_json(row[0]) if row else None

    def _list(self, kind: str, model: type[T]) -> list[T]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM objects WHERE kind=? ORDER BY id", (kind,)
            ).fetchall()
        return [model.model_validate_json(row[0]) for row in rows]

    def put_source(self, source: SourceDocument) -> None:
        self._put("source", source.id, source)

    def get_source(self, source_id: str) -> SourceDocument | None:
        return self._get("source", source_id, SourceDocument)

    def list_sources(self) -> list[SourceDocument]:
        return self._list("source", SourceDocument)

    def put_questionnaire(self, questionnaire: Questionnaire) -> None:
        self._put("questionnaire", questionnaire.id, questionnaire)

    def get_questionnaire(self, questionnaire_id: str) -> Questionnaire | None:
        return self._get("questionnaire", questionnaire_id, Questionnaire)

    def put_answer(self, answer: DraftAnswer) -> None:
        self._put("answer", answer.id, answer)

    def get_answer(self, answer_id: str) -> DraftAnswer | None:
        return self._get("answer", answer_id, DraftAnswer)

    def list_answers(self, questionnaire_id: str | None = None) -> list[DraftAnswer]:
        answers = self._list("answer", DraftAnswer)
        return (
            [item for item in answers if item.questionnaire_id == questionnaire_id]
            if questionnaire_id is not None
            else answers
        )

    def put_review(self, review: ReviewDecision) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO review_decisions(id,answer_id,payload) VALUES(?,?,?)",
                    (review.id, review.answer_id, review.model_dump_json()),
                )
        except sqlite3.IntegrityError as exc:
            raise InvalidTransitionError(f"review decision already exists: {review.id}") from exc

    def get_review_for_answer(self, answer_id: str) -> ReviewDecision | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload FROM review_decisions
                WHERE answer_id=? ORDER BY sequence DESC LIMIT 1
                """,
                (answer_id,),
            ).fetchone()
        return ReviewDecision.model_validate_json(row[0]) if row else None

    def list_reviews_for_answer(self, answer_id: str) -> list[ReviewDecision]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM review_decisions
                WHERE answer_id=? ORDER BY sequence
                """,
                (answer_id,),
            ).fetchall()
        return [ReviewDecision.model_validate_json(row[0]) for row in rows]

    def append_audit(self, event: AuditEvent) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_events(sequence,payload) VALUES(?,?)",
                (event.sequence, event.model_dump_json()),
            )

    def append_audit_event(
        self,
        event_type: str,
        entity_id: str,
        payload: dict[str, object],
    ) -> AuditEvent:
        for attempt in range(5):
            try:
                with self._connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    return _SQLiteTransaction(connection).append_audit_event(
                        event_type,
                        entity_id,
                        payload,
                    )
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).casefold() or attempt == 4:
                    raise
                time.sleep(0.02 * (2**attempt))
        raise RuntimeError("unreachable")

    def list_audit(self) -> list[AuditEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM audit_events ORDER BY sequence"
            ).fetchall()
        return [AuditEvent.model_validate_json(row[0]) for row in rows]
