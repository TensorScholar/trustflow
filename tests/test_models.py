from datetime import datetime

import pytest
from pydantic import ValidationError

from trustflow.domain.models import SourceDocument


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceDocument.model_validate(
            {
                "id": "s",
                "title": "S",
                "owner": "o",
                "version": "1",
                "content": "x",
                "source_uri": "p://s",
                "extra": True,
            }
        )


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceDocument(
            id="s",
            title="S",
            owner="o",
            version="1",
            content="x",
            source_uri="p://s",
            updated_at=datetime.now(),
        )
