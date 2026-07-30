# Implementation risk register

| Risk | Failure mode | Practical mitigation | Evidence required |
|---|---|---|---|
| Malicious document | Macro, malformed ZIP, or decompression bomb | reject macros; member, file-size, and expansion ceilings | hostile fixture tests |
| Formula injection | Exported cell executes in spreadsheet | neutralize `=`, `+`, `-`, and `@` prefixes | round-trip tests |
| Unsupported claim | LLM invents an answer | evidence-only generation; no evidence means unanswerable | unsupported-answer metric |
| Stale evidence | Old policy is reused | owner/version/freshness metadata and impact scan | source-change tests |
| Conflicting sources | Two policies disagree | conservative conflict status and human review | polarity/conflict tests |
| Sensitive auto-approval | Legal/security claim bypasses reviewer | deterministic sensitivity gate | labeled sensitivity corpus |
| Formatting damage | Export corrupts workbook or document | copy original, edit targeted locations, round-trip fixtures | sample-file tests |
| Parser ambiguity | Question locations are unstable | explicit location model and deterministic IDs per import | parser contract tests |
| Cross-deal leakage | Future hosted search mixes tenants | tenant key at repository boundary before multi-tenancy | isolation tests before hosting |
| Prompt injection in source | Document tells model to ignore controls | source text is evidence, never executable instruction | adversarial source tests |
| OCR error | Scanned PDF produces wrong text | OCR explicitly unsupported in v0.1 | format limitation |
| Audit mutation | Review history is edited | hash chain and external-head recommendation | tamper tests |
| Connector privilege | Drive/SharePoint connector reads too much | scoped connector port and AgentGuard integration | connector threat review |
| Over-engineering | Browser extension and connector catalog delay core | ship file workflow first | roadmap review |
