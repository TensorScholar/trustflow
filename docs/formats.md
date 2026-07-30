# Format support

## XLSX

Questions are cells ending in `?`; answers are written to the next cell. Workbook formulas
and macros are not executed. `.xlsm` is not accepted.

## DOCX

Questions are paragraphs or table cells ending in `?`. Paragraph answers are inserted below
the question. Table questions are exported as appended review text in v0.1.

## CSV

Questions are cells ending in `?`; answers are written to the next column with formula
neutralization.

## JSON

Accepts a list of strings or `{"questions": [...]}`.

## Markdown

Accepts lines ending in `?`.

## PDF

Only text-extractable PDFs are parsed. The output is a JSON claim ledger.
