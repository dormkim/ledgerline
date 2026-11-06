"""Second cold review (2026-11-06 evening). Each test is one probe that used to fail or was unchecked."""
from app import llm, pipeline


def run(bank, ledger, answers=None):
    return pipeline.run(bank, ledger, answers, use_llm=False)


# Two money-like columns: value checks cannot tell which one is the amount, so the agent asks.
BANK = "a,b,c\n2026-10-01,100.00,7.50\n2026-10-02,250.50,3.25\n2026-10-03,80.00,9.99\n"
LEDGER = "Date,Amount,Name\n2026-10-01,100.00,Acme\n2026-10-02,250.50,Beta\n2026-10-03,80.00,Gamma\n"


def test_unclear_columns_ask_first():
    r = run(BANK, LEDGER)
    assert r["status"] == "needs_input" and r["questions"][0]["missing"] == ["amount"]


def test_user_mapping_that_fits_the_values_is_used():
    r = run(BANK, LEDGER, {"mapping": {"bank": {"amount": "b"}}})
    assert r["status"] == "done" and len(r["matches"]) == 3
    assert r["columns"]["bank"]["how"]["amount"] == "user"


def test_user_mapping_that_does_not_fit_is_not_used_and_says_why():
    # A date column picked as the amount used to be taken as is (every row then unreadable).
    # Now the question comes back with the reason, and nothing is computed from the wrong column.
    r = run(BANK, LEDGER, {"mapping": {"bank": {"amount": "a"}}})
    assert r["status"] == "needs_input"
    q = r["questions"][0]
    assert q["missing"] == ["amount"]
    assert q["answer_not_used"] == ["amount = 'a' (values are not amounts)"]


def test_wrong_user_mapping_is_overridden_by_values_and_reported():
    r = run("a,b\n2026-10-01,100.00\n2026-10-02,250.50\n", LEDGER, {"mapping": {"bank": {"date": "b", "amount": "a"}}})
    step = next(s for s in r["trace"] if s["step"] == "map bank columns")
    assert step["mapping"]["date"] == "a" and step["mapping"]["amount"] == "b"
    assert len(step["answer_not_used"]) == 2


def test_cut_off_reasoning_is_not_parsed_as_json():
    assert llm.parse_json('<think>the user wants {"mapping": {"date": "a"}} maybe') is None
    assert llm.parse_json('<think>ok</think>{"mapping": {"date": "a"}}') == {"mapping": {"date": "a"}}


def test_eval_waits_out_the_rate_limit_instead_of_crashing(monkeypatch):
    import io
    import urllib.error
    import urllib.request

    from eval import run_eval

    calls, slept = [], []

    def fake_urlopen(req, timeout=None, context=None):
        calls.append(1)
        if len(calls) <= 2:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO(b""))
        return io.BytesIO(b'{"status": "done"}')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(run_eval.time, "sleep", slept.append)
    req = urllib.request.Request("http://x/api/runs", data=b"{}")
    assert run_eval._post(req, False) == {"status": "done"}
    assert slept == [60, 120] and sum(run_eval._post.__defaults__[0]) > 600
