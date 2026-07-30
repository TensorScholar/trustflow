# Integration contracts

## Answer generator

Receives one question and evidence. It cannot query sources, approve claims, or export files.

## Parser

Returns stable question IDs and source locations. It must not execute document code.

## Exporter

Writes only final answer text and visible source metadata. It neutralizes spreadsheet
formula prefixes.

## Portfolio integrations

- ProofDiff can regression-test answer behavior.
- PermitDiff can track policy changes that invalidate answer libraries.
- AgentGuard can authorize connector and export actions.
- InferenceLedger can measure cost per accepted answer or completed questionnaire.
