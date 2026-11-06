# Eval: holdout (HTTP https://localhost, LLM on)

- cases passed (everything exact): **10/10**
- matches: precision 44/44, recall 44/44
- exceptions: precision 21/21, recall 21/21
- response time ms: median 1527, max 2001

| case | pass | ms | status | matches tp/exp/got | exceptions tp/exp/got | narrative | notes |
|---|---|---|---|---|---|---|---|
| 01_bank_preamble_lines | yes | 1866 | done | 4/4/4 | 3/3/3 | {'llm': 3} |  |
| 02_tab_separated_trailing_minus | yes | 1211 | done | 5/5/5 | 2/2/2 | {'llm': 2} |  |
| 03_drcr_indicator_parentheses | yes | 1828 | done | 7/7/7 | 3/3/3 | {'llm': 3} |  |
| 04_debit_credit_balance_bill_type | yes | 1461 | done | 6/6/6 | 2/2/2 | {'llm': 2} |  |
| 05_late_payment_and_vendor_refund | yes | 1527 | done | 6/6/6 | 2/2/2 | {'llm': 2} |  |
| 06_unreadable_amount_and_date | yes | 2001 | done | 5/5/5 | 4/4/4 | {'llm': 4} |  |
| 07_day_month_undecidable | yes | 9 | needs_input | 0/0/0 | 0/0/0 | {} |  |
| 08_identical_payments_real_and_duplicate | yes | 1499 | done | 7/7/7 | 2/2/2 | {'llm': 2} |  |
| 09_spanish_bank_french_ledger_ambiguous | yes | 1925 | needs_input | 4/4/4 | 3/3/3 | {'llm': 3} |  |
| 10_two_amount_like_columns | yes | 1384 | needs_input | 0/0/0 | 0/0/0 | {} |  |
