from datetime import UTC, datetime
from pathlib import Path

import pytest

from trustflow.adapters.exporters import ExporterRegistry
from trustflow.adapters.parsers import ParserRegistry
from trustflow.domain.errors import UnsafeExportError
from trustflow.domain.models import AnswerStatus, DraftAnswer, Evidence


def test_export_preserves_destination_created_concurrently(tmp_path, monkeypatch) -> None:
    source = tmp_path / "q.json"
    source.write_text('{"questions":["Question?"]}', encoding="utf-8")
    questionnaire = ParserRegistry().parse(source)
    answer = DraftAnswer(
        questionnaire_id=questionnaire.id,
        question_id="q1",
        text="Answer",
        status=AnswerStatus.ANSWERED,
        confidence=1,
        evidence=(
            Evidence(
                source_id="source",
                source_title="Source",
                source_uri="policy://source",
                source_version="1",
                source_digest="a" * 64,
                owner="owner",
                excerpt="Approved evidence.",
                score=1,
                updated_at=datetime.now(UTC),
            ),
        ),
    )
    output = tmp_path / "out.json"

    def competing_create(_temporary: Path, destination: Path) -> None:
        destination.write_text("concurrent owner", encoding="utf-8")
        raise FileExistsError

    monkeypatch.setattr("trustflow.adapters.exporters.os.link", competing_create)

    with pytest.raises(UnsafeExportError, match="created concurrently"):
        ExporterRegistry().export(questionnaire, [answer], {}, output)

    assert output.read_text(encoding="utf-8") == "concurrent owner"
