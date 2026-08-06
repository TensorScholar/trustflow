import csv
import json

from docx import Document
from openpyxl import Workbook, load_workbook

from trustflow.adapters.exporters import ExporterRegistry
from trustflow.adapters.parsers import ParserRegistry
from trustflow.domain.models import AnswerStatus, DraftAnswer


def answer(questionnaire_id, question_id, text) -> DraftAnswer:
    return DraftAnswer(
        questionnaire_id=questionnaire_id,
        question_id=question_id,
        text=text,
        status=AnswerStatus.ANSWERED,
        confidence=1,
    )


def test_xlsx_export_neutralizes_formula(tmp_path) -> None:
    source = tmp_path / "q.xlsx"
    workbook = Workbook()
    workbook.active["A1"] = "Question?"
    workbook.save(source)
    questionnaire = ParserRegistry().parse(source)
    output = tmp_path / "out.xlsx"
    ExporterRegistry().export(
        questionnaire,
        [answer(questionnaire.id, "q1", "=HYPERLINK(\"bad\")")],
        {},
        output,
    )
    assert load_workbook(output).active["B1"].value.startswith("'")


def test_csv_export(tmp_path) -> None:
    source = tmp_path / "q.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(["Question?"])
    questionnaire = ParserRegistry().parse(source)
    output = tmp_path / "out.csv"
    ExporterRegistry().export(
        questionnaire,
        [answer(questionnaire.id, "q1", "Answer")],
        {},
        output,
    )
    assert "Answer" in output.read_text(encoding="utf-8")


def test_docx_export(tmp_path) -> None:
    source = tmp_path / "q.docx"
    document = Document()
    document.add_paragraph("Question?")
    document.save(source)
    questionnaire = ParserRegistry().parse(source)
    output = tmp_path / "out.docx"
    ExporterRegistry().export(
        questionnaire,
        [answer(questionnaire.id, "q1", "Answer")],
        {},
        output,
    )
    assert "Answer" in Document(output).paragraphs[0].text


def test_json_export(tmp_path) -> None:
    source = tmp_path / "q.json"
    source.write_text('{"questions":["Question?"]}', encoding="utf-8")
    questionnaire = ParserRegistry().parse(source)
    output = tmp_path / "out.json"
    ExporterRegistry().export(
        questionnaire,
        [answer(questionnaire.id, "q1", "Answer")],
        {},
        output,
    )
    assert json.loads(output.read_text(encoding="utf-8"))[0]["answer"] == "Answer"


def test_formula_neutralization_with_leading_whitespace(tmp_path) -> None:
    source = tmp_path / "q.csv"
    source.write_text("Question?\n", encoding="utf-8")
    questionnaire = ParserRegistry().parse(source)
    output = tmp_path / "out.csv"
    ExporterRegistry().export(
        questionnaire,
        [answer(questionnaire.id, "q1", "\t=HYPERLINK(\"bad\")")],
        {},
        output,
    )
    assert "'\t=HYPERLINK" in output.read_text(encoding="utf-8")


def test_export_refuses_to_overwrite_source(tmp_path) -> None:
    import pytest

    from trustflow.domain.errors import UnsafeExportError

    source = tmp_path / "q.json"
    original = '{"questions":["Question?"]}'
    source.write_text(original, encoding="utf-8")
    questionnaire = ParserRegistry().parse(source)
    with pytest.raises(UnsafeExportError, match="must differ"):
        ExporterRegistry().export(
            questionnaire,
            [answer(questionnaire.id, "q1", "Answer")],
            {},
            source,
        )
    assert source.read_text(encoding="utf-8") == original


def test_docx_nested_table_round_trip(tmp_path) -> None:
    source = tmp_path / "nested.docx"
    document = Document()
    outer = document.add_table(rows=1, cols=1)
    nested = outer.cell(0, 0).add_table(rows=1, cols=1)
    nested.cell(0, 0).paragraphs[0].text = "Nested question?"
    document.save(source)
    questionnaire = ParserRegistry().parse(source)
    assert len(questionnaire.questions) == 1
    output = tmp_path / "nested-out.docx"
    ExporterRegistry().export(
        questionnaire,
        [answer(questionnaire.id, "q1", "Nested answer")],
        {},
        output,
    )
    reopened = Document(output)
    nested_output = reopened.tables[0].cell(0, 0).tables[0].cell(0, 0).text
    assert "Nested answer" in nested_output


def test_exporter_defense_in_depth_blocks_unreviewed_status(tmp_path) -> None:
    import pytest

    from trustflow.domain.errors import InvalidTransitionError

    source = tmp_path / "q.json"
    source.write_text('{"questions":["Sensitive question?"]}', encoding="utf-8")
    questionnaire = ParserRegistry().parse(source)
    unresolved = DraftAnswer(
        questionnaire_id=questionnaire.id,
        question_id="q1",
        text="Draft",
        status=AnswerStatus.REVIEW_REQUIRED,
        confidence=0.8,
    )
    with pytest.raises(InvalidTransitionError, match="unresolved"):
        ExporterRegistry().export(
            questionnaire,
            [unresolved],
            {},
            tmp_path / "out.json",
        )
