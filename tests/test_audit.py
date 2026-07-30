import pytest

from trustflow.domain.audit import make_event, verify_chain
from trustflow.domain.errors import IntegrityError


def test_audit_chain() -> None:
    event = make_event(
        sequence=1,
        event_type="x",
        entity_id="x",
        payload={"a": 1},
        previous_hash="0" * 64,
    )
    verify_chain([event])


def test_audit_tamper() -> None:
    event = make_event(
        sequence=1,
        event_type="x",
        entity_id="x",
        payload={"a": 1},
        previous_hash="0" * 64,
    )
    with pytest.raises(IntegrityError):
        verify_chain([event.model_copy(update={"payload": {"a": 2}})])
