import hashlib
import json
from datetime import UTC, datetime
from typing import Iterable

from trustflow.domain.errors import IntegrityError
from trustflow.domain.models import AuditEvent


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def make_event(
    *,
    sequence: int,
    event_type: str,
    entity_id: str,
    payload: dict[str, object],
    previous_hash: str,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    timestamp = occurred_at or datetime.now(UTC)
    body = {
        "sequence": sequence,
        "event_type": event_type,
        "entity_id": entity_id,
        "payload": payload,
        "occurred_at": timestamp.astimezone(UTC).isoformat(),
        "previous_hash": previous_hash,
    }
    digest = hashlib.sha256(canonical_json(body).encode()).hexdigest()
    return AuditEvent(
        sequence=sequence,
        event_type=event_type,
        entity_id=entity_id,
        payload=payload,
        occurred_at=timestamp,
        previous_hash=previous_hash,
        event_hash=digest,
    )


def verify_chain(events: Iterable[AuditEvent]) -> None:
    previous = "0" * 64
    sequence = 1
    for event in events:
        if event.sequence != sequence or event.previous_hash != previous:
            raise IntegrityError("audit chain sequence mismatch")
        expected = make_event(
            sequence=event.sequence,
            event_type=event.event_type,
            entity_id=event.entity_id,
            payload=event.payload,
            previous_hash=event.previous_hash,
            occurred_at=event.occurred_at,
        )
        if expected.event_hash != event.event_hash:
            raise IntegrityError("audit event hash mismatch")
        previous = event.event_hash
        sequence += 1
