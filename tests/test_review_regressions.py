"""Defects found by the independent review (2026-11-06). Each test is one probe that used to fail."""
from app import pipeline
from app.numcheck import evidence, bad_numbers


def run(bank, ledger, answers=None):
    return pipeline.run(bank, ledger, answers, use_llm=False)


def pairs(r):
    return sorted((tuple(b["row"] for b in m["bank"]), tuple(l["row"] for l in m["ledger"])) for m in r["matches"])


def kinds(r):
    return sorted(e["kind"] for e in r["exceptions"])


def test_unicode_and_inner_minus_signs_do_not_flip_the_ledger():
    bank = "Date,Description,Amount\n2026-01-05,STAPLES,−50.00\n2026-01-06,UBER,$-20.00\n2026-01-07,ACME,100.00\n"
    ledger = "Date,Name,Amount\n2026-01-05,Staples,-50\n2026-01-06,Uber,-20\n2026-01-07,Acme,100\n"
    r = run(bank, ledger)
    assert len(r["matches"]) == 3 and r["exceptions"] == []


def test_dot_thousands_in_whole_number_column():
    bank = "Buchungstag;Verwendungszweck;Betrag\n05.01.2026;ACME;1.500\n06.01.2026;BETA;2.000\n"
    ledger = "Datum;Name;Betrag\n05.01.2026;Acme;1500\n06.01.2026;Beta;2000\n"
    assert len(run(bank, ledger)["matches"]) == 2


def test_header_words_are_not_currencies():
    r = run("Date,Description,Amt\n2026-01-05,ACME,1200.00\n", "Date,Name,Amount\n2026-01-05,Acme,€1200.00\n")
    assert len(r["matches"]) == 1 and list(r["totals"]) == ["EUR"]


def test_short_reference_digits_do_not_create_a_mismatch():
    r = run("Date,Description,Amount\n2026-01-05,COFFEE SUITE 12,37.20\n",
            "Date,Num,Name,Amount\n2026-01-05,INV-0012,Client,500.00\n")
    assert kinds(r) == ["unmatched_bank", "unmatched_ledger"]


def test_ambiguous_split_holds_rows_and_takes_a_combination_answer():
    bank = "Date,Description,Amount\n" + "".join(f"2026-01-0{d},ACME LTD,{a}\n" for d, a in [(5, 100), (6, 200), (7, 120), (8, 180)])
    ledger = "Date,Name,Amount\n2026-01-05,Acme Ltd,300\n"
    r = run(bank, ledger)
    assert [q["type"] for q in r["questions"]] == ["ambiguous_match"] and r["exceptions"] == []
    r2 = run(bank, ledger, {"pairs": [{"bank": [1, 2], "ledger": [1]}]})
    assert ((1, 2), (1,)) in pairs(r2) and kinds(r2) == ["unmatched_bank", "unmatched_bank"]


def test_wrong_answer_becomes_a_visible_mismatch_not_a_match():
    bank = "Date,Description,Amount\n2026-01-05,X,100\n"
    r = run(bank, "Date,Name,Amount\n2026-01-05,Y,300\n", {"pairs": [{"bank": 1, "ledger": 1}]})
    assert r["matches"] == [] and kinds(r) == ["amount_mismatch"]


def test_greedy_does_not_strand_a_valid_pairing():
    bank = "Date,Description,Amount\n2026-01-05,TRANSFER,500.00\n2026-01-12,TRANSFER,500.00\n"
    ledger = "Date,Name,Amount\n2026-01-06,Northwind,500.00\n2025-12-30,Contoso,500.00\n"
    r = run(bank, ledger)
    assert len(r["matches"]) == 2 and r["exceptions"] == []


def test_different_invoice_numbers_are_not_duplicates():
    bank = "Date,Description,Amount\n2026-01-05,ACME INV-1042,250.00\n2026-01-05,ACME INV-1043,250.00\n"
    r = run(bank, "Date,Num,Name,Amount\n2026-01-05,INV-1042,Acme,250.00\n")
    assert kinds(r) == ["unmatched_bank"]


def test_reversal_in_money_in_column_keeps_its_sign():
    bank = "Date,Description,Paid in,Paid out\n2026-01-05,REVERSAL,-75.00,\n"
    r = run(bank, "Date,Name,Amount\n2026-01-05,Reversal,-75.00\n")
    assert len(r["matches"]) == 1


def test_bad_inputs_are_errors_not_crashes():
    led = "Date,Name,Amount\n2026-01-05,A,1\n"
    assert run('Date,Amount\n2026-01-05,"1\n' + "x" * 200_000, led)["status"] == "error"
    assert run("Date,Description,Amount\n1/1/99999999999999999999,A,1\n2026-01-05,B,2\n", led)["status"] == "done"
    for bad in ({"mapping": {"bank": "x"}}, {"mapping": []}, {"date_format": "dmy"}, {"pairs": [1]}, {"pairs": "x"}):
        assert run("Date,Description,Amount\n2026-01-05,A,1\n", led, bad)["status"] in {"done", "needs_input"}


def test_invented_money_and_percent_are_caught():
    allowed, money, pct = evidence({"ref": "INV-1042", "amount": "1200.00", "days_overdue": 12, "due": "2026-02-14",
                               "due_source": "invoice date + 30 days"})
    assert bad_numbers("The total outstanding is 1,042 EUR.", allowed, money) == ["1,042"]
    assert bad_numbers("A late fee of 30 EUR.", allowed, money) == ["30"]
    assert bad_numbers("Pay 1200.00 EUR plus 2%.", allowed, money, pct) == ["2"]
    # ...but a percentage the bank text itself states may be quoted (found with the LLM on, case 06).
    ev = evidence({"desc": "RE 2026-0822 abzgl. 3% Skonto", "amount": "2910.00"})
    assert bad_numbers("The bank text cites a 3% Skonto.", *ev) == []
    assert bad_numbers("Invoice INV-1042 for EUR 1,200.00 is 12 days overdue since February 14, 2026.", allowed, money) == []
