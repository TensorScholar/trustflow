"""Safe questionnaire exporters."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from docx import Document
from openpyxl import load_workbook

from trustflow.adapters.safety import neutralize_spreadsheet_formula
from trustflow.domain.errors import UnsupportedFormatError
from trustflow.domain.models import (
    AnswerStatus,
    DocumentFormat,
    DraftAnswer,
    ExportResult,
    Questionnaire,
    ReviewDecision,
)


def _final_text(answer: DraftAnswer, review: ReviewDecision | None) -> str:
    return review.final_text if review is not None else answer.text


class ExporterRegistry:
    def export(
        self,
        questionnaire: Questionnaire,
        answers: list[DraftAnswer],
        reviews: dict[str, ReviewDecision],
        output: Path,
    ) -> ExportResult:
        mapping = {item.question_id: item for item in answers}
        if questionnaire.format is DocumentFormat.XLSX:
            self._xlsx(questionnaire, mapping, reviews, output)
        elif questionnaire.format is DocumentFormat.DOCX:
            self._docx(questionnaire, mapping, reviews, output)
        elif questionnaire.format is DocumentFormat.CSV:
            self._csv(questionnaire, mapping, reviews, output)
        elif questionnaire.format in {
            DocumentFormat.JSON,
            DocumentFormat.MARKDOWN,
            DocumentFormat.PDF,
        }:
            self._json(questionnaire, mapping, reviews, output)
        else:
            raise UnsupportedFormatError(questionnaire.format.value)
        return ExportResult(
            questionnaire_id=questionnaire.id,
            output_path=str(output),
            format=questionnaire.format,
            answered=sum(item.status is AnswerStatus.ANSWERED for item in answers),
            review_required=sum(
                item.status in {AnswerStatus.REVIEW_REQUIRED, AnswerStatus.CONFLICT}
                for item in answers
            ),
            unanswerable=sum(
                item.status in {AnswerStatus.UNANSWERABLE, AnswerStatus.STALE} for item in answers
            ),
        )

    def _xlsx(
        self,
        questionnaire: Questionnaire,
        answers: dict[str, DraftAnswer],
        reviews: dict[str, ReviewDecision],
        output: Path,
    ) -> None:
        shutil.copyfile(questionnaire.source_path, output)
        workbook = load_workbook(output)
        for question in questionnaire.questions:
            answer = answers[question.id]
            sheet = workbook[question.location.sheet or workbook.active.title]
            cell = sheet[question.location.cell or "A1"]
            target = sheet.cell(row=cell.row, column=cell.column + 1)
            target.value = neutralize_spreadsheet_formula(
                _final_text(answer, reviews.get(answer.id))
            )
        workbook.save(output)

    def _docx(
        self,
        questionnaire: Questionnaire,
        answers: dict[str, DraftAnswer],
        reviews: dict[str, ReviewDecision],
        output: Path,
    ) -> None:
        document = Document(questionnaire.source_path)
        for question in questionnaire.questions:
            answer = answers[question.id]
            text = _final_text(answer, reviews.get(answer.id))
            if question.location.paragraph is not None:
                paragraph = document.paragraphs[question.location.paragraph]
                paragraph.add_run(f"\nAnswer: {text}")
            else:
                document.add_paragraph(f"{question.text}\nAnswer: {text}")
        document.save(output)

    def _csv(
        self,
        questionnaire: Questionnaire,
        answers: dict[str, DraftAnswer],
        reviews: dict[str, ReviewDecision],
        output: Path,
    ) -> None:
        with Path(questionnaire.source_path).open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.reader(handle))
        for question in questionnaire.questions:
            answer = answers[question.id]
            row = (question.location.row or 1) - 1
            column = int(question.location.key or "0") + 1
            while len(rows[row]) <= column:
                rows[row].append("")
            rows[row][column] = neutralize_spreadsheet_formula(
                _final_text(answer, reviews.get(answer.id))
            )
        with output.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(rows)

    def _json(
        self,
        questionnaire: Questionnaire,
        answers: dict[str, DraftAnswer],
        reviews: dict[str, ReviewDecision],
        output: Path,
    ) -> None:
        payload = []
        for question in questionnaire.questions:
            answer = answers[question.id]
            payload.append(
                {
                    "question_id": question.id,
                    "question": question.text,
                    "answer": _final_text(answer, reviews.get(answer.id)),
                    "status": answer.status.value,
                    "sources": [
                        {
                            "id": item.source_id,
                            "version": item.source_version,
                            "uri": item.source_uri,
                        }
                        for item in answer.evidence
                    ],
                }
            )
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
