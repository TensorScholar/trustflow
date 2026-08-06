# Implementation risk register

| Risk | Failure mode | Practical mitigation | Evidence required |
|---|---|---|---|
| Malicious document | Macro, malformed ZIP, traversal member, corrupt entry, or decompression bomb | reject macros, encrypted members, unsafe paths, duplicates, corrupt entries, and files beyond member/count/size/ratio ceilings | hostile fixture tests |
| Formula injection | Exported cell executes in spreadsheet | neutralize `=`, `+`, `-`, and `@` after leading whitespace/control prefixes | round-trip tests |
| Review bypass | Sensitive, stale, conflicting, rejected, or unsupported draft is exported | fail-closed service gate; unanswerable drafts require explicit edit | negative export tests |
| Source mutation | Export overwrites or partially corrupts the imported questionnaire | reject same-path destinations and atomically replace completed output | same-path and round-trip tests |
| Unsupported claim | Generator invents an answer | evidence-only generation; no evidence means unanswerable | unsupported-answer metric |
| Stale evidence | Old policy is reused | owner/version/freshness metadata and impact scan | source-change tests |
| Conflicting sources | Two policies disagree | conservative conflict status and human review | polarity/conflict tests |
| Sensitive auto-approval | Legal/security claim bypasses reviewer | deterministic sensitivity gate and export gate | labeled sensitivity corpus |
| Parser ambiguity | Question locations are unstable | explicit location model and deterministic IDs per import | parser contract tests |
| API file disclosure | Remote caller reads arbitrary server-local files | multipart upload only; generated storage names; local path omitted from response | API negative tests |
| Audit race | Concurrent writers create duplicate sequence numbers | SQLite `BEGIN IMMEDIATE` transaction and retry | concurrent writer test |
| Cross-deal leakage | Future hosted search mixes tenants | tenant key at repository boundary before multi-tenancy | isolation tests before hosting |
| Prompt injection in source | Document tells model to ignore controls | source text is evidence, never executable instruction | adversarial source tests |
| OCR error | Scanned PDF produces wrong text | OCR explicitly unsupported in v0.1 | format limitation |
| Audit mutation | Review history is edited | hash chain and external-head recommendation | tamper tests |
| Connector privilege | Drive/SharePoint connector reads too much | scoped connector port and authorization layer | connector threat review |
