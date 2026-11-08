# Eval: cases (HTTP https://64-176-236-185.sslip.io, LLM on)

- cases passed (everything exact): **10/10**
- matches: precision 63/63, recall 63/63
- exceptions: precision 24/24, recall 24/24
- response time ms: median 2255, max 3082

| case | pass | ms | status | matches tp/exp/got | exceptions tp/exp/got | narrative | notes |
|---|---|---|---|---|---|---|---|
| 01_quickbooks_us_basic | yes | 1935 | done | 9/9/9 | 3/3/3 | {'llm': 3} |  |
| 02_xero_gbp_split_debit_credit | yes | 1541 | done | 8/8/8 | 2/2/2 | {'llm': 2} |  |
| 03_bank_fee_shortfall_partial | yes | 3082 | done | 6/6/6 | 4/4/4 | {'llm': 4} |  |
| 04_duplicate_bank_line_au | yes | 2271 | done | 9/9/9 | 3/3/3 | {'llm': 3} |  |
| 05_ambiguous_tie_txnamt | yes | 2255 | needs_input | 7/7/7 | 3/3/3 | {'llm': 3} |  |
| 06_german_semicolon_eur | yes | 2784 | done | 8/8/8 | 3/3/3 | {'llm': 3} |  |
| 07_multicurrency_usd_eur | yes | 1986 | done | 8/8/8 | 4/4/4 | {'llm': 4} |  |
| 08_cad_installments_three_way_split | yes | 1543 | done | 8/8/8 | 2/2/2 | {'llm': 2} |  |
| 09_header_only_bank | yes | 46 | error | 0/0/0 | 0/0/0 | {} |  |
| 10_meaningless_headers | yes | 2262 | needs_input | 0/0/0 | 0/0/0 | {} |  |
