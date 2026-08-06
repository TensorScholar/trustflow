# Format support

## XLSX

Questions are cells ending in `?`; answers are written to the next cell. Workbook formulas
and macros are not executed. `.xlsm` is not accepted. Formula-like answer text is prefixed
with an apostrophe, including when dangerous prefixes follow leading whitespace.

## DOCX

Questions are paragraphs or table-cell paragraphs ending in `?`. Answers are inserted at the
recorded paragraph location, including nested tables.

## CSV

Questions are cells ending in `?`; answers are written to the next column with formula
neutralization.

## JSON

Accepts a list of strings or `{"questions": [...]}`.

## Markdown

Accepts lines ending in `?`.

## PDF

Only text-extractable PDFs are parsed. Page count is bounded. The output is a JSON claim ledger;
the source PDF is never mutated.
