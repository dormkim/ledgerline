from pathlib import Path

from app import narrate, pipeline

ROOT = Path(__file__).resolve().parents[1]
BANK = (ROOT / "samples/us_quickbooks/bank.csv").read_text()
LEDGER = (ROOT / "samples/us_quickbooks/ledger.csv").read_text()


def _rules(r):
    return sorted(m["rule"] for m in r["matches"])


def test_demo_run_offline():
    r = pipeline.run(BANK, LEDGER, use_llm=False)
    assert r["status"] == "needs_input"  # the 750.00 tie is asked, not guessed
    assert [q["type"] for q in r["questions"]] == ["ambiguous_match"]
    kinds = [e["kind"] for e in r["exceptions"]]
    assert kinds.count("amount_mismatch") == 1 and kinds.count("possible_duplicate") == 1
    assert "R3 split sum" in _rules(r)
    assert r["totals"]["EUR"]["net_difference"] == "1.12"
    assert all(e["narrative"]["source"] == "template" for e in r["exceptions"])


def test_answering_the_tie_resolves_it():
    r = pipeline.run(BANK, LEDGER, {"pairs": [{"bank": 8, "ledger": 10}]}, use_llm=False)
    assert r["status"] == "done"
    assert "user-confirmed" in _rules(r)
    assert any(f["counterparty"] == "Granite Labs" for f in r["followups"])


def test_currencies_never_mix():
    bank = "Date,Description,Amount,Currency\n2026-10-01,ACME,500.00,USD\n"
    ledger = "Date,Name,Amount,Currency\n2026-10-01,Acme,500.00,EUR\n"
    r = pipeline.run(bank, ledger, use_llm=False)
    assert r["matches"] == [] and set(r["totals"]) == {"USD", "EUR"}


def test_empty_file_is_an_error_not_all_clear():
    r = pipeline.run("Date,Amount\n", LEDGER, use_llm=False)
    assert r["status"] == "error" and "no transactions" in r["error"]


def test_unreadable_row_is_reported():
    bank = "Date,Description,Amount\n2026-10-03,ACME CORP INV-1042,4200.00\n2026-10-04,???,n/a\n"
    r = pipeline.run(bank, LEDGER, use_llm=False)
    assert any(e["kind"] == "unreadable_row" and e["bank"][0]["row"] == 2 for e in r["exceptions"])


def test_llm_sentence_with_invented_number_is_dropped(monkeypatch):
    def fake(system, user, **kw):
        if "reminder" in system:
            return {"drafts": [{"id": "F1", "subject": "Reminder", "body": "Please pay 1100.00 plus a 55.00 late fee."}]}, {"ms": 1, "error": None}
        return {"items": [{"id": "E1", "explanation": "Short by 15.00. That is about 42% of the invoice.",
                           "next_step": "Ask Delta Freight."}]}, {"ms": 1, "error": None}
    monkeypatch.setattr(narrate.llm, "chat_json", fake)
    r = pipeline.run(BANK, LEDGER)
    e1 = next(e for e in r["exceptions"] if e["id"] == "E1")
    assert e1["narrative"]["source"] == "llm-checked"
    assert e1["narrative"]["removed"] == ["That is about 42% of the invoice."]
    f1 = next(f for f in r["followups"] if f["id"] == "F1")
    assert f1["draft"]["source"] == "template" and "55.00" in f1["draft"]["note"]


def test_llm_down_falls_back_visibly(monkeypatch):
    monkeypatch.setattr(narrate.llm, "chat_json", lambda *a, **k: (None, {"ms": 5, "error": "HTTP 503 from LLM endpoint"}))
    r = pipeline.run(BANK, LEDGER)
    e = r["exceptions"][0]["narrative"]
    assert e["source"] == "template" and e["note"] == "HTTP 503 from LLM endpoint"
    step = next(s for s in r["trace"] if s["step"].startswith("explain"))
    assert step["status"] == "fallback"
