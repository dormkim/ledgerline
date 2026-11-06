"""HTTP API + static UI. One process, one container, runs on a Vultr VM."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel, Field

from . import export, llm, pipeline, store

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT.parent / "samples"
VERSION = "0.2.0"
# Demo data sets: (folder, label). The first one is the default and the one in the demo video.
SAMPLE_SETS = {
    "us_quickbooks": "US bank + QuickBooks-style ledger (USD and EUR)",
    "de_bank_semicolon": "German bank export (; and 1.234,56) + Xero-style invoices",
    "uk_bank_paid_in_out": "UK bank (Paid in / Paid out, dd/mm) + Sage-style ledger",
}
# No inline scripts or styles anywhere in the UI, so the policy can be strict.
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
                               "frame-ancestors 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}
RATE = (20, 600)  # 20 runs per 10 minutes per client: protects inference credits on a public URL

app = FastAPI(title="Ledgerline: reconciliation agent", version=VERSION)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def _headers(request: Request, call_next):
    resp = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    if request.url.path.startswith("/api/runs"):
        resp.headers["Cache-Control"] = "no-store"  # run bodies hold uploaded financial rows
    return resp


class Pair(BaseModel):
    bank: list[int] | int
    ledger: list[int] | int


class Answers(BaseModel):
    """What the user told the agent after it asked. Typed, so malformed answers are a 422, not a crash."""
    mapping: dict[Literal["bank", "ledger"], dict[str, str]] = Field(default_factory=dict)
    date_format: dict[Literal["bank", "ledger"], Literal["dmy", "mdy", "ymd"]] = Field(default_factory=dict)
    pairs: list[Pair] = Field(default_factory=list, max_length=200)


class RunIn(BaseModel):
    bank_csv: str = Field(max_length=2_000_000)
    ledger_csv: str = Field(max_length=2_000_000)
    answers: Answers = Field(default_factory=Answers)
    parent: str | None = Field(default=None, max_length=40)


def _limit(req: Request) -> None:
    # req.client is the real peer: uvicorn rewrites it from X-Forwarded-For only for trusted proxies
    # (FORWARDED_ALLOW_IPS), so a client cannot dodge the limit by sending its own header.
    ip = req.client.host if req.client else "?"
    now = time.time()
    for k in [k for k, v in _hits.items() if not v or now - v[-1] > RATE[1]]:
        del _hits[k]
    q = _hits[ip]
    while q and now - q[0] > RATE[1]:
        q.popleft()
    if len(q) >= RATE[0]:
        raise HTTPException(429, "Too many runs from this address; try again in a few minutes.")
    q.append(now)


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/healthz")
def health():
    return {"ok": True, "version": VERSION, "llm": llm.public_status()}


@app.get("/api/samples")
def samples():
    return [{"id": k, "label": v} for k, v in SAMPLE_SETS.items()]


@app.get("/api/demo")
def demo(set: str = "us_quickbooks"):  # noqa: A002 — query parameter name seen by clients
    if set not in SAMPLE_SETS:
        raise HTTPException(404, "unknown sample set")
    folder = SAMPLES / set
    return {"set": set, "label": SAMPLE_SETS[set],
            "bank_csv": (folder / "bank.csv").read_text(), "ledger_csv": (folder / "ledger.csv").read_text()}


@app.post("/api/runs")
def create_run(body: RunIn, req: Request):
    _limit(req)
    result = pipeline.run(body.bank_csv, body.ledger_csv, body.answers.model_dump())
    result["llm"] = llm.public_status()
    result["id"] = store.save_run(result, body.parent)
    return result


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    r = store.get_run(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return r | {"audit": store.audit(run_id)}


@app.post("/api/runs/{run_id}/followups/{fid}/approve")
def approve(run_id: str, fid: str):
    r = store.get_run(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    f = next((x for x in r.get("followups", []) if x["id"] == fid), None)
    if not f:
        raise HTTPException(404, "follow-up not found")
    if f.get("status") != "draft":
        raise HTTPException(409, f"already {f.get('status')}")  # one decision per draft in the audit log
    f["status"] = "approved (not sent: no mail integration in this demo)"
    store.update_run(run_id, r)
    store.record(run_id, "approve_followup", {"id": fid, "to": f["counterparty"], "amount": f["amount"],
                                              "currency": f["currency"], "subject": f["draft"]["subject"]})
    return {"ok": True, "followup": f, "audit": store.audit(run_id)}


@app.get("/api/runs/{run_id}/export.csv")
def export_csv(run_id: str):
    r = store.get_run(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return Response(export.to_csv(r), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ledgerline-{run_id[:8]}.csv"'})
