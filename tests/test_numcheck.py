from app.numcheck import allowed_numbers, bad_numbers, keep_supported

FACTS = {"bank_amount": "1485.00", "ledger_amount": "1500.00", "difference": "-15.00", "date": "2026-10-10", "ref": "INV-1046"}


def test_numbers_from_evidence_pass():
    allowed = allowed_numbers(FACTS)
    assert bad_numbers("Received 1,485.00 against 1500.00 on 2026-10-10 for INV-1046, short by 15.00.", allowed) == []


def test_invented_number_is_removed():
    text, removed = keep_supported("Short by 15.00. That is 1% of the invoice.", allowed_numbers(FACTS))
    assert text == "Short by 15.00."
    assert removed == ["That is 1% of the invoice."]


def test_llm_arithmetic_is_not_trusted():
    # 1500 - 1485 = 15 is in the facts; 2985 (a sum the LLM made up) is not.
    assert bad_numbers("Together that is 2,985.00.", allowed_numbers(FACTS)) == ["2,985.00"]
