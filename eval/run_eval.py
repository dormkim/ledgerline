"""Score the agent on eval/cases/*. Cases were written blind (by a separate agent that never saw app/).

Usage: python -m eval.run_eval [--llm] [--url http://127.0.0.1:8080] [--out eval/results_<tag>]
Without --url the pipeline runs in-process; with --url it goes through the HTTP API like a judge would.
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))


def _groups(items, kind_filter=None):
    out = set()
    for m in items:
        b = tuple(sorted(m.get("bank", [])))
        l = tuple(sorted(m.get("ledger", [])))
        out.add((b, l))
    return out


def _exc_keys(items):
    keys = set()
    for e in items:
        bank = e.get("bank", [])
        b = (bank[0] if isinstance(bank[0], int) else bank[0]["row"]) if bank else None
        led = e.get("ledger", [])
        l = (led[0] if isinstance(led[0], int) else led[0]["row"]) if led else None
        diff = e.get("difference") or (e.get("facts") or {}).get("difference")
        keys.add((e["kind"], b, l, diff if e["kind"] == "amount_mismatch" else None))
    return keys


def _rows(cards):
    return [c["row"] for c in cards]


def actual_view(r: dict) -> dict:
    return {"error": r.get("status") == "error",
            "questions": sorted({q["type"] for q in r.get("questions", [])}),
            "matched": [{"bank": _rows(m["bank"]), "ledger": _rows(m["ledger"])} for m in r.get("matches", [])],
            "exceptions": r.get("exceptions", []), "totals": r.get("totals", {})}


def score(exp: dict, act: dict) -> dict:
    em, am = _groups(exp.get("matched", [])), _groups(act["matched"])
    ee, ae = _exc_keys(exp.get("exceptions", [])), _exc_keys(act["exceptions"])
    tot_bad = []
    for cur, vals in (exp.get("totals") or {}).items():
        for k, v in vals.items():
            got = act["totals"].get(cur, {}).get(k)
            if got is None or float(got) != float(v):
                tot_bad.append(f"{cur}.{k}: expected {v}, got {got}")
    exp_q = sorted(q if isinstance(q, str) else (q.get("type") or q.get("kind")) for q in exp.get("questions", []))
    ok = (exp.get("error", False) == act["error"] and exp_q == act["questions"]
          and em == am and ee == ae and not tot_bad)
    return {"pass": ok, "match_tp": len(em & am), "match_exp": len(em), "match_got": len(am),
            "exc_tp": len(ee & ae), "exc_exp": len(ee), "exc_got": len(ae),
            "missing_matches": sorted(map(str, em - am)), "extra_matches": sorted(map(str, am - em)),
            "missing_exc": sorted(map(str, ee - ae)), "extra_exc": sorted(map(str, ae - ee)),
            "error_ok": exp.get("error", False) == act["error"],
            "questions_ok": exp_q == act["questions"], "totals_bad": tot_bad}


def run_case(case: Path, url: str | None, use_llm: bool, insecure: bool = False) -> tuple[dict, float]:
    bank, ledger = (case / "bank.csv").read_text(encoding="utf-8"), (case / "ledger.csv").read_text(encoding="utf-8")
    t0 = time.perf_counter()
    if url:
        req = urllib.request.Request(url.rstrip("/") + "/api/runs", data=json.dumps(
            {"bank_csv": bank, "ledger_csv": ledger}).encode(), headers={"Content-Type": "application/json"})
        r = _post(req, insecure)
    else:
        from app import pipeline
        r = pipeline.run(bank, ledger, use_llm=use_llm)
    return r, (time.perf_counter() - t0) * 1000


def _post(req: urllib.request.Request, insecure: bool, waits: tuple[int, ...] = (60, 120, 240, 300)) -> dict:
    """POST one case. The public app allows 20 runs per 10 minutes per address, so both sets in a row
    hit 429. Wait (12 minutes in all, longer than the window) and retry instead of crashing halfway."""
    ctx = ssl._create_unverified_context() if insecure else None  # local Caddy uses its own CA
    for wait in (*waits, None):
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                raise
            print(f"  rate limited (429), waiting {wait} s", file=sys.stderr)
            time.sleep(wait)
    raise AssertionError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--url")
    ap.add_argument("--insecure", action="store_true", help="accept a self-signed cert (local Caddy)")
    # Default name must not be "results": on macOS (case-insensitive) results.md overwrote RESULTS.md.
    ap.add_argument("--out", help="output path without extension (default eval/local_<cases>)")
    ap.add_argument("--cases", default="cases", help="cases (first blind set) or holdout (second blind set)")
    a = ap.parse_args()
    a.out = a.out or str(ROOT / f"local_{a.cases}")
    rows = []
    for case in sorted((ROOT / a.cases).iterdir()):
        if not case.is_dir():
            continue
        exp = json.loads((case / "expected.json").read_text())
        try:
            r, ms = run_case(case, a.url, a.llm, a.insecure)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            # One unreachable case is a failed case in the report, not a crash that hides the other results.
            r, ms = {"status": f"request failed: {type(e).__name__} {getattr(e, 'code', '')}".strip()}, 0.0
        s = score(exp, actual_view(r))
        narr = [e.get("narrative", {}).get("source") for e in r.get("exceptions", [])]
        rows.append({"case": case.name, "ms": round(ms), "status": r.get("status"), **s,
                     "narrative_sources": {k: narr.count(k) for k in set(narr)},
                     "llm_removed": next((st.get("llm_sentences_removed") for st in r.get("trace", [])
                                          if st["step"].startswith("explain")), None)})
    Path(a.out + ".json").write_text(json.dumps(rows, indent=1))
    _report(rows, a)


def _report(rows: list[dict], a) -> None:
    n = len(rows)
    passed = sum(r["pass"] for r in rows)
    tp, exp_, got = (sum(r[k] for r in rows) for k in ("match_tp", "match_exp", "match_got"))
    etp, eexp, egot = (sum(r[k] for r in rows) for k in ("exc_tp", "exc_exp", "exc_got"))
    ms = sorted(r["ms"] for r in rows)
    lines = [f"# Eval: {a.cases} ({'HTTP ' + a.url if a.url else 'in-process'}, LLM {'on' if a.llm or a.url else 'off'})", "",
             f"- cases passed (everything exact): **{passed}/{n}**",
             f"- matches: precision {tp}/{got}, recall {tp}/{exp_}",
             f"- exceptions: precision {etp}/{egot}, recall {etp}/{eexp}",
             f"- response time ms: median {ms[n // 2]}, max {ms[-1]}", "",
             "| case | pass | ms | status | matches tp/exp/got | exceptions tp/exp/got | narrative | notes |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        notes = "; ".join(filter(None, [
            ("missing " + ", ".join(r["missing_matches"] + r["missing_exc"])) if r["missing_matches"] or r["missing_exc"] else "",
            ("extra " + ", ".join(r["extra_matches"] + r["extra_exc"])) if r["extra_matches"] or r["extra_exc"] else "",
            "" if r["questions_ok"] else "questions differ", "" if r["error_ok"] else "error flag differs",
            "; ".join(r["totals_bad"])]))
        lines.append(f"| {r['case']} | {'yes' if r['pass'] else 'NO'} | {r['ms']} | {r['status']} | "
                     f"{r['match_tp']}/{r['match_exp']}/{r['match_got']} | {r['exc_tp']}/{r['exc_exp']}/{r['exc_got']} | "
                     f"{r['narrative_sources']} | {notes[:300]} |")
    text = "\n".join(lines) + "\n"
    Path(a.out + ".md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
