from datetime import UTC, datetime

import pytest

from trustflow.adapters.exporters import ExporterRegistry
from trustflow.adapters.generator import ExtractiveAnswerGenerator
from trustflow.adapters.memory import MemoryStore
from trustflow.adapters.parsers import ParserRegistry
from trustflow.application.service import TrustFlowService
from trustflow.domain.models import SourceDocument


@pytest.fixture
def service() -> TrustFlowService:
    service = TrustFlowService(
        store=MemoryStore(),
        parser=ParserRegistry(),
        exporter=ExporterRegistry(),
        generator=ExtractiveAnswerGenerator(),
    )
    service.ingest_source(
        SourceDocument(
            id="security",
            title="Security standard",
            owner="security",
            version="1",
            content="Customer data is encrypted at rest with AES-256 and in transit with TLS 1.3.",
            source_uri="policy://security",
            updated_at=datetime.now(UTC),
            tags=frozenset({"encryption", "customer", "data", "rest", "transit"}),
        )
    )
    service.ingest_source(
        SourceDocument(
            id="legal",
            title="Legal policy",
            owner="legal",
            version="1",
            content=(
                "Indemnity terms require legal review and are defined in the governing contract."
            ),
            source_uri="policy://legal",
            updated_at=datetime.now(UTC),
            tags=frozenset({"indemnity", "legal", "contract"}),
        )
    )
    return service
