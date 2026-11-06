"""Product surface added on 2026-11-06: sample sets, summary numbers, CSV export, headers, one approval per draft."""
import csv
import io

from fastapi.testclient import TestClient

from app import export, main, pipeline


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return TestClient(main.app)


def test_every_sample_set_runs_and_needs_no_column_question(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    sets = c.get("/api/samples").json()
    assert [s["id"] for s in sets][0] == "us_quickbooks" and len(sets) == 3
    for s in sets:
        r = c.post("/api/runs", json={k: v for k, v in c.get(f"/api/demo?set={s['id']}").json().items()
                                      if k.endswith("_csv")}).json()
        assert r["status"] in ("done", "needs_input"), r.get("error")
        assert all(q["type"] == "ambiguous_match" for q in r["questions"])
        assert r["overview"]["match_groups"] >= 3 and r["overview"]["exceptions"] >= 1
    assert c.get("/api/demo?set=../etc").status_code == 404


def test_payment_on_due_date_matches_and_gets_no_reminder():
    # Quill & Co: invoiced 22/09, due 22/10, paid 21/10 without a reference. Counting days from the invoice
    # date left it unmatched and drafted a reminder to a customer who had paid.
    d = "samples/uk_bank_paid_in_out/"
    r = pipeline.run(open(d + "bank.csv").read(), open(d + "ledger.csv").read(), use_llm=False)
    assert "Quill & Co" not in [f["counterparty"] for f in r["followups"]]
    m = next(m for m in r["matches"] if m["ledger"][0]["name"] == "Quill & Co")
    assert m["evidence"]["days_counted_from"] == "due date" and m["evidence"]["days_apart"] == -1


def test_overview_counts_match_the_lists():
    d = "samples/us_quickbooks/"
    r = pipeline.run(open(d + "bank.csv").read(), open(d + "ledger.csv").read(), use_llm=False)
    o = r["overview"]
    assert o["exceptions"] == len(r["exceptions"]) and o["followups"] == len(r["followups"])
    assert o["match_groups"] == len(r["matches"]) and o["questions"] == len(r["questions"])
    assert o["matched_bank_lines"] == sum(len(m["bank"]) for m in r["matches"])
    assert o["overdue_by_currency"] == {"USD": "3500.00"}


def test_export_csv_keeps_numbers_and_defuses_formulas(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    demo = c.get("/api/demo").json()
    r = c.post("/api/runs", json={"bank_csv": demo["bank_csv"], "ledger_csv": demo["ledger_csv"]}).json()
    resp = c.get(f"/api/runs/{r['id']}/export.csv")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(resp.text.lstrip("﻿"))))
    assert sum(x["section"] == "exception" for x in rows) == len(r["exceptions"])
    e1 = next(x for x in rows if x["id"] == "E1")
    assert (e1["bank_amount"], e1["ledger_amount"], e1["difference"]) == ("1485.00", "1500.00", "-15.00")
    assert export._safe("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")" and export._safe("-199.00") == "-199.00"
    assert export._safe("-1+1") == "'-1+1"
    assert c.get("/api/runs/nope/export.csv").status_code == 404


def test_security_headers_and_no_cache_on_runs(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    h = c.get("/").headers
    assert "default-src 'self'" in h["content-security-policy"] and h["x-content-type-options"] == "nosniff"
    demo = c.get("/api/demo").json()
    r = c.post("/api/runs", json={"bank_csv": demo["bank_csv"], "ledger_csv": demo["ledger_csv"]})
    assert r.headers["cache-control"] == "no-store"


def test_a_draft_is_approved_once(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    demo = c.get("/api/demo").json()
    r = c.post("/api/runs", json={"bank_csv": demo["bank_csv"], "ledger_csv": demo["ledger_csv"]}).json()
    assert c.post(f"/api/runs/{r['id']}/followups/F1/approve").status_code == 200
    assert c.post(f"/api/runs/{r['id']}/followups/F1/approve").status_code == 409
    assert [a["action"] for a in c.get(f"/api/runs/{r['id']}").json()["audit"]] == ["run", "approve_followup"]
