# Format support

TrustFlow fingerprints the exact questionnaire bytes at import. Export fails closed if the source
file is missing, has changed since import, lacks a recorded fingerprint, or if the requested
output path already exists. This keeps recorded question locations bound to the exact source
artifact that was parsed.

## XLSX

Questions are visible cells ending in `?`; questions on hidden sheets, hidden rows, or hidden
columns are rejected rather than silently processed. Answers are written to the first writable
cell immediately to the right of the question or, for a merged question range, immediately to
the right of that merged range. TrustFlow refuses to overwrite an occupied or merged answer
target. Workbook formulas and macros are not executed. `.xlsm` is not accepted. Formula-like
answer text is prefixed with an apostrophe, including when dangerous prefixes follow leading
whitespace.

## DOCX

Questions are paragraphs or table-cell paragraphs ending in `?`. Answers are inserted at the
recorded paragraph location, including nested tables. The source document fingerprint must still
match the imported artifact when export is finalized.

## CSV

Questions are cells ending in `?`; answers are written to the next column with formula
neutralization. A non-empty adjacent cell is treated as an occupied target and is never silently
overwritten.

## JSON

Accepts a list of strings or `{"questions": [...]}`. Export is a JSON claim ledger rather than a
mutation of the source questionnaire.

## Markdown

Accepts lines ending in `?`. Export is a JSON claim ledger rather than a mutation of the source
questionnaire.

## PDF

Only text-extractable PDFs are parsed. Page count is bounded. OCR is not implemented. The output
is a JSON claim ledger; the source PDF is never mutated.
