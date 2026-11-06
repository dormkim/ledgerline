import os

from fastapi.testclient import TestClient

from app import main


def test_health_never_exposes_key(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "sk-secret-123")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    monkeypatch.delenv("LLM_DISABLED")
    body = TestClient(main.app).get("/healthz").text
    assert "sk-secret-123" not in body and "configured" in body
    monkeypatch.setenv("LLM_DISABLED", "1")


def test_run_and_approve(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    c = TestClient(main.app)
    demo = c.get("/api/demo").json()
    r = c.post("/api/runs", json=demo | {"answers": {"pairs": [{"bank": 8, "ledger": 10}]}}).json()
    assert r["status"] == "done"
    a = c.post(f"/api/runs/{r['id']}/followups/F1/approve").json()
    assert a["followup"]["status"].startswith("approved")
    assert [x["action"] for x in a["audit"]] == ["run", "approve_followup"]
    assert c.get(f"/api/runs/{r['id']}").json()["followups"][0]["status"].startswith("approved")
    assert c.get("/api/runs").status_code in (404, 405)  # no public listing of other people's runs
    assert os.environ["LLM_DISABLED"] == "1"


def test_malformed_answers_are_rejected_not_crashing(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    c = TestClient(main.app)
    demo = c.get("/api/demo").json()
    for bad in ({"mapping": {"bank": "x"}}, {"date_format": "dmy"}, {"pairs": [1]}, {"pairs": [{"bank": "a", "ledger": 1}]}):
        assert c.post("/api/runs", json=demo | {"answers": bad}).status_code == 422


def test_old_runs_are_purged(tmp_path, monkeypatch):
    from app import store
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    old = store.save_run({"status": "done"}, None)
    with store._db() as con:
        con.execute("update runs set created = datetime('now', '-25 hours') where id = ?", (old,))
    store.save_run({"status": "done"}, None)
    assert store.get_run(old) is None
