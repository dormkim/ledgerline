# Eval (in-process, LLM off)

- cases passed (everything exact): **8/10**
- matches: precision 59/59, recall 59/63
- exceptions: precision 22/26, recall 22/24
- response time ms: median 1, max 11

| case | pass | ms | status | matches tp/exp/got | exceptions tp/exp/got | narrative | notes |
|---|---|---|---|---|---|---|---|
| 01_quickbooks_us_basic | yes | 11 | done | 9/9/9 | 3/3/3 | {'template': 3} |  |
| 02_xero_gbp_split_debit_credit | yes | 1 | done | 8/8/8 | 2/2/2 | {'template': 2} |  |
| 03_bank_fee_shortfall_partial | yes | 1 | done | 6/6/6 | 4/4/4 | {'template': 4} |  |
| 04_duplicate_bank_line_au | yes | 1 | done | 9/9/9 | 3/3/3 | {'template': 3} |  |
| 05_ambiguous_tie_txnamt | NO | 1 | needs_input | 6/7/6 | 2/3/2 | {'template': 2} | missing ((5,), (6,)), ('unmatched_ledger', None, 7, None) |
| 06_german_semicolon_eur | yes | 1 | done | 8/8/8 | 3/3/3 | {'template': 3} |  |
| 07_multicurrency_usd_eur | yes | 1 | done | 8/8/8 | 4/4/4 | {'template': 4} |  |
| 08_cad_installments_three_way_split | NO | 1 | done | 5/8/5 | 1/2/5 | {'template': 5} | missing ((1, 4), (1,)), ((6,), (5,)), ((9,), (8, 9, 10)), ('unmatched_ledger', None, 11, None); extra ('unmatched_bank', 1, None, None), ('unmatched_bank', 4, None, None), ('unmatched_bank', 6, None, None), ('unmatched_bank', 9, None, None) |
| 09_header_only_bank | yes | 0 | error | 0/0/0 | 0/0/0 | {} |  |
| 10_meaningless_headers | yes | 1 | needs_input | 0/0/0 | 0/0/0 | {} |  |
