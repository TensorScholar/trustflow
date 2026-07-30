from pathlib import Path

from trustflow.adapters.exporters import ExporterRegistry
from trustflow.adapters.generator import ExtractiveAnswerGenerator
from trustflow.adapters.memory import MemoryStore
from trustflow.adapters.parsers import ParserRegistry
from trustflow.adapters.sqlite import SQLiteStore
from trustflow.application.service import TrustFlowService


def build_service(database: str | Path | None = None) -> TrustFlowService:
    return TrustFlowService(
        store=SQLiteStore(database) if database else MemoryStore(),
        parser=ParserRegistry(),
        exporter=ExporterRegistry(),
        generator=ExtractiveAnswerGenerator(),
    )
