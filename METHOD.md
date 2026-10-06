# What this prototype measures

CallLens evaluates call transcripts and optionally transcribes uploaded audio. The offline evaluator is a deliberately limited phrase-based baseline. Live mode uses a structured LLM judgment, validates the four expected rubric dimensions, and verifies that supporting quotations occur in the input. Quote matching does not prove the interpretation is correct.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Acknowledgement | Dismissive response | Generic acknowledgement | Specific acknowledgement |
| Action clarity | Unusable or contradictory step | Partial step | Executable next step |
| Outcome confirmation | Explicit failure | Agent-only success claim | Customer confirms success |
| Handoff | Explicitly failed required handoff | Transfer mentioned | Owner/channel plus timing/reference |

Unavailable or inapplicable dimensions are **unknown**, never automatically zero. The score is `sum(observed scores) / (2 × number of observed dimensions) × 100`. It is a review aid with equal weights, not a validated business KPI. Compare scores only after checking coverage. Offline rules award only the subset they can detect and leave everything else unknown.

**Business outcome:** resolved, unresolved, escalated or unknown, with transcript evidence. A promised refund does not establish a completed refund. Customer-reported resolution is not verified in CRM records. No customer satisfaction score, containment rate, compliance claim or financial impact is fabricated.

**Speech recognition:** optional word error rate uses word-level edit distance divided by reference word count. Comparison lowercases text, removes punctuation and speaker labels, and retains apostrophes within words. Numbers and contractions are not semantically normalized. For uploaded audio it uses the original ASR text. A human reference is required. WER may exceed 100% and does not measure meaning preservation.

**Timing:** displayed time measures evaluator processing only. Agent response latency needs real turn timestamps. TTS naturalness, interruptions, speaker diarization and audio quality are outside this version.

**Data:** bundled calls are synthetic. The application writes no transcripts or keys to disk automatically. Live mode sends authorized content to OpenAI. Provider retention and account settings still apply; `store=False` on the evaluation request is not a zero-retention guarantee. Downloaded reports include the transcript. Keep them private when using authorized nonpublic data. Do not deploy a key-backed public instance without access control and rate limits.

**Validation:** six authored examples cover basic intent/outcome behaviour; they are not a held-out benchmark. Automated tests check metric arithmetic, missing data, contradictory outcomes, evidence validation, export handling and mocked provider failures. Human review is required for decisions. Prompt instructions reduce injection risk but cannot guarantee immunity.

**Next experiment:** create 20 additional synthetic calls without changing the rules, label them manually before running either evaluator, compare intent accuracy and an outcome confusion matrix, inspect disagreements, and record model, prompt version, coverage and request usage. Keep training and evaluation examples separate.
