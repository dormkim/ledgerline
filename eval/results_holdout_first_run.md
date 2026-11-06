# Eval: holdout (in-process, LLM off)

- cases passed (everything exact): **8/10**
- matches: precision 42/42, recall 42/44
- exceptions: precision 20/23, recall 20/21
- response time ms: median 1, max 11

| case | pass | ms | status | matches tp/exp/got | exceptions tp/exp/got | narrative | notes |
|---|---|---|---|---|---|---|---|
| 01_bank_preamble_lines | yes | 11 | done | 4/4/4 | 3/3/3 | {'template': 3} |  |
| 02_tab_separated_trailing_minus | yes | 1 | done | 5/5/5 | 2/2/2 | {'template': 2} |  |
| 03_drcr_indicator_parentheses | yes | 1 | done | 7/7/7 | 3/3/3 | {'template': 3} |  |
| 04_debit_credit_balance_bill_type | yes | 1 | done | 6/6/6 | 2/2/2 | {'template': 2} |  |
| 05_late_payment_and_vendor_refund | yes | 1 | done | 6/6/6 | 2/2/2 | {'template': 2} |  |
| 06_unreadable_amount_and_date | yes | 1 | done | 5/5/5 | 4/4/4 | {'template': 4} |  |
| 07_day_month_undecidable | yes | 0 | needs_input | 0/0/0 | 0/0/0 | {} |  |
| 08_identical_payments_real_and_duplicate | NO | 1 | needs_input | 5/7/5 | 2/2/3 | {'template': 3} | missing ((2,), (2,)), ((3,), (3,)); extra ('possible_duplicate', 3, None, None); questions differ |
| 09_spanish_bank_french_ledger_ambiguous | NO | 1 | needs_input | 4/4/4 | 2/3/4 | {'template': 4} | missing ('amount_mismatch', 8, 7, '-100.00'); extra ('unmatched_bank', 8, None, None), ('unmatched_ledger', None, 7, None) |
| 10_two_amount_like_columns | yes | 1 | needs_input | 0/0/0 | 0/0/0 | {} |  |
