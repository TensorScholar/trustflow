"""Questionnaire parsers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from uuid import uuid4

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

from trustflow.adapters.safety import inspect_document
from trustflow.domain.classification import classify_sensitivity
from trustflow.domain.errors import UnsupportedFormatError
from trustflow.domain.models import (
    DocumentFormat,
    PolicySettings,
    Question,
    Questionnaire,
    QuestionLocation,
)


def _question(identifier: str, text: str, location: QuestionLocation) -> Question:
    return Question(
        id=identifier,
        text=text.strip(),
        location=location,
        sensitivity=classify_sensitivity(text),
    )


class ParserRegistry:
    def __init__(self, policy: PolicySettings | None = None) -> None:
        self.policy = policy or PolicySettings()

    def parse(self, path: Path) -> Questionnaire:
        fmt = inspect_document(path, self.policy)
        if fmt is DocumentFormat.XLSX:
            questions = self._xlsx(path)
        elif fmt is DocumentFormat.DOCX:
            questions = self._docx(path)
        elif fmt is DocumentFormat.CSV:
            questions = self._csv(path)
        elif fmt is DocumentFormat.JSON:
            questions = self._json(path)
        elif fmt is DocumentFormat.MARKDOWN:
            questions = self._markdown(path)
        elif fmt is DocumentFormat.PDF:
            questions = self._pdf(path)
        else:
            raise UnsupportedFormatError(fmt.value)
        return Questionnaire(
            id=f"qnr_{uuid4().hex}",
            title=path.stem,
            source_path=str(path),
            format=fmt,
            questions=tuple(questions),
        )

    def _xlsx(self, path: Path) -> list[Question]:
        workbook = load_workbook(path, read_only=True, data_only=False, keep_links=False)
        questions: list[Question] = []
        index = 1
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    value = cell.value
                    if isinstance(value, str) and value.strip().endswith("?"):
                        questions.append(
                            _question(
                                f"q{index}",
                                value,
                                QuestionLocation(
                                    format=DocumentFormat.XLSX,
                                    sheet=sheet.title,
                                    cell=cell.coordinate,
                                ),
                            )
                        )
                        index += 1
        return questions

    def _docx(self, path: Path) -> list[Question]:
        document = Document(path)
        questions: list[Question] = []
        for index, paragraph in enumerate(document.paragraphs):
            text = paragraph.text.strip()
            if text.endswith("?"):
                questions.append(
                    _question(
                        f"q{len(questions)+1}",
                        text,
                        QuestionLocation(format=DocumentFormat.DOCX, paragraph=index),
                    )
                )
        for table_index, table in enumerate(document.tables):
            for row_index, row in enumerate(table.rows):
                for cell_index, cell in enumerate(row.cells):
                    text = cell.text.strip()
                    if text.endswith("?"):
                        questions.append(
                            _question(
                                f"q{len(questions)+1}",
                                text,
                                QuestionLocation(
                                    format=DocumentFormat.DOCX,
                                    key=f"table:{table_index}:{row_index}:{cell_index}",
                                ),
                            )
                        )
        return questions

    def _csv(self, path: Path) -> list[Question]:
        questions: list[Question] = []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row_index, row in enumerate(csv.reader(handle), start=1):
                for cell_index, value in enumerate(row):
                    if value.strip().endswith("?"):
                        questions.append(
                            _question(
                                f"q{len(questions)+1}",
                                value,
                                QuestionLocation(
                                    format=DocumentFormat.CSV,
                                    row=row_index,
                                    key=str(cell_index),
                                ),
                            )
                        )
        return questions

    def _json(self, path: Path) -> list[Question]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["questions"] if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("JSON questionnaire must contain a list of questions")
        questions = []
        for index, row in enumerate(rows):
            text = row["question"] if isinstance(row, dict) else row
            if not isinstance(text, str):
                raise ValueError("question must be a string")
            questions.append(
                _question(
                    f"q{index+1}",
                    text,
                    QuestionLocation(format=DocumentFormat.JSON, key=str(index)),
                )
            )
        return questions

    def _markdown(self, path: Path) -> list[Question]:
        questions = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            text = line.lstrip("#-* 0123456789.").strip()
            if text.endswith("?"):
                questions.append(
                    _question(
                        f"q{len(questions)+1}",
                        text,
                        QuestionLocation(format=DocumentFormat.MARKDOWN, row=line_number),
                    )
                )
        return questions

    def _pdf(self, path: Path) -> list[Question]:
        reader = PdfReader(path)
        questions = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for line in text.splitlines():
                cleaned = line.strip()
                if cleaned.endswith("?"):
                    questions.append(
                        _question(
                            f"q{len(questions)+1}",
                            cleaned,
                            QuestionLocation(
                                format=DocumentFormat.PDF,
                                row=page_number,
                            ),
                        )
                    )
        return questions
