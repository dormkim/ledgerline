# Eval: cases (HTTP https://localhost, LLM on)

- cases passed (everything exact): **10/10**
- matches: precision 63/63, recall 63/63
- exceptions: precision 24/24, recall 24/24
- response time ms: median 1654, max 2203

| case | pass | ms | status | matches tp/exp/got | exceptions tp/exp/got | narrative | notes |
|---|---|---|---|---|---|---|---|
| 01_quickbooks_us_basic | yes | 1654 | done | 9/9/9 | 3/3/3 | {'llm': 3} |  |
| 02_xero_gbp_split_debit_credit | yes | 1379 | done | 8/8/8 | 2/2/2 | {'llm': 2} |  |
| 03_bank_fee_shortfall_partial | yes | 2203 | done | 6/6/6 | 4/4/4 | {'llm': 4} |  |
| 04_duplicate_bank_line_au | yes | 1863 | done | 9/9/9 | 3/3/3 | {'llm': 3} |  |
| 05_ambiguous_tie_txnamt | yes | 1459 | needs_input | 7/7/7 | 3/3/3 | {'llm': 3} |  |
| 06_german_semicolon_eur | yes | 1898 | done | 8/8/8 | 3/3/3 | {'llm': 3} |  |
| 07_multicurrency_usd_eur | yes | 1808 | done | 8/8/8 | 4/4/4 | {'llm': 4} |  |
| 08_cad_installments_three_way_split | yes | 1356 | done | 8/8/8 | 2/2/2 | {'llm': 2} |  |
| 09_header_only_bank | yes | 8 | error | 0/0/0 | 0/0/0 | {} |  |
| 10_meaningless_headers | yes | 1294 | needs_input | 0/0/0 | 0/0/0 | {} |  |
