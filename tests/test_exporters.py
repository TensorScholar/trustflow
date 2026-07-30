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
