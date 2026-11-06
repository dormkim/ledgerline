# Evaluation results

Both case sets were written by a separate agent that never saw `app/` (blind). Each was scored on first
sight, before any fix, and the first-sight score is kept below as the honest number.

| Set | First sight (code never saw it) | After fixing what it exposed | Through the Docker + HTTPS stack, LLM on |
|---|---|---|---|
| `cases/` (10) | **8/10** exact | 10/10 | 10/10, median 1.7 s, max 2.2 s per run |
| `holdout/` (10, written after the first fixes) | **8/10** exact | 10/10 | 10/10, median 1.5 s, max 2.0 s per run |

"Exact" means every match group, every exception (kind, rows, difference), every question type and the
error flag equal the expected file. Matching alone takes 1–15 ms; the rest is the two parallel LLM calls.

What the first sight exposed, and the fix:

| Case | Failure | Fix |
|---|---|---|
| cases/05 | `Txn Desc` header not recognised, so the bank lost all reference evidence and two resolvable ties were asked as questions | `desc` header patterns; if no text column is found by name, the first mostly-text column is used |
| cases/08 | `Payments` not recognised as money-out; `$` read as USD in a Canadian file | header patterns; `$` no longer implies a currency (USD/CAD/AUD all use it) |
| holdout/08 | two genuine identical rent debits: one was flagged as a duplicate because duplicates were set aside before matching | match first; a repeated line is a suspected duplicate only if it found no ledger line of its own; identical candidates are interchangeable, not ambiguous |
| holdout/09 | French/Spanish headers (`N° pièce`, `Tiers`) not mapped; the year inside `FA-2026/0431` counted as a shared reference | FR/ES header patterns; a bare year is never reference evidence |

Found later, with the LLM on (DeepSeek through the same OpenAI-compatible client, as a stand-in until the
Vultr Inference key exists): in cases/06 the checker removed two correct sentences because they quoted
"3% Skonto" from the bank text, and percentages were banned outright. Now a percentage is allowed only when
the evidence itself states it (`tests/test_review_regressions.py`).

An independent code review (a separate agent, read-only) then found 15 defects that no case covered:
Unicode/inner minus signs, `1.500` as thousands, header words read as currencies, short references
colliding, ambiguous split payments not held, greedy matching stranding a valid pair, duplicates ignoring
invoice numbers, reversals losing their sign, a too-generous number checker, quadratic work on big files,
a spoofable rate limit, unlimited retention of uploaded rows, and three crash paths. Each one is now a
regression test in `tests/test_review_regressions.py` or `tests/test_api.py`, and both case sets still pass.

Reproduce:

```
LLM_DISABLED=1 python -m eval.run_eval --cases cases          # in-process, code only
python -m eval.run_eval --cases holdout --url https://<host>   # like a judge, through the public URL
```

Result files: `results_first_blind_run.md`, `results_holdout_first_run.md` (first sight),
`results_https_llm_cases.md`, `results_https_llm_holdout.md` (full stack).
