"""The agent's workflow: read → understand columns → normalise → match → explain → draft follow-ups.

Each step lands in `trace` with its duration and what it decided. When a step cannot decide safely
it stops and returns a `question` instead of guessing; the client answers and re-runs.
"""
from __future__ import annotations

import logging
import time
from collections import Counter

from . import columns, llm_columns, reconcile
from .narrate import narrate
from .reader import CREDIT_WORDS, DEBIT_WORDS, Sheet, build, payable_kind, resolve_order
from .table import InputError, read_rows


log = logging.getLogger("ledgerline")
MATCH_BUDGET_S = 20.0


class Trace:
    def __init__(self):
        self.steps: list[dict] = []
        self.t0 = time.perf_counter()

    def step(self, name: str, t: float, status: str = "ok", **detail):
        self.steps.append({"step": name, "status": status, "ms": round((time.perf_counter() - t) * 1000), **detail})

    def total(self) -> int:
        return round((time.perf_counter() - self.t0) * 1000)


def run(bank_csv, ledger_csv, answers: dict | None = None, use_llm: bool = True) -> dict:
    answers = answers or {}
    tr = Trace()
    try:
        out = _run(bank_csv, ledger_csv, answers, use_llm, tr)
    except InputError as e:
        out = {"status": "error", "error": str(e)}
        tr.step("stopped", tr.t0, "failed", detail=str(e))
    except Exception as e:  # noqa: BLE001 — a bug must surface as a visible error, not a 500 or an empty result
        log.exception("pipeline crashed")
        out = {"status": "error", "error": f"Internal error ({type(e).__name__}). Nothing was reconciled."}
        tr.step("stopped", tr.t0, "failed", detail=type(e).__name__)
    out["trace"] = tr.steps
    out["total_ms"] = tr.total()
    return out


def _understand(side, data, answers, use_llm, tr) -> tuple[list, list, dict, dict] | dict:
    t = time.perf_counter()
    headers, rows, delim = read_rows(data, f"{side} file")
    tr.step(f"read {side} file", t, rows=len(rows), columns=len(headers), delimiter=repr(delim))
    t = time.perf_counter()
    found = columns.from_headers(headers)
    _type_as_flag(found, headers, rows)
    how = {k: "header" for k in found}
    mapping_answer = (answers.get("mapping") or {}).get(side) if isinstance(answers.get("mapping"), dict) else None
    for role, h in (mapping_answer if isinstance(mapping_answer, dict) else {}).items():
        if h in headers:
            found = {k: v for k, v in found.items() if v != h} | {role: h}
            how[role] = "user"
    filled = columns.from_values(headers, rows, found)
    how |= {k: "values" for k in filled if k not in found}
    found = filled
    need = columns.missing(found)
    if need:
        # The LLM only pre-fills the answer. A column choice decides every number downstream,
        # so a person confirms it — even when the LLM's pick passes the value checks.
        suggestion, meta = llm_columns.propose(side, headers, rows, found) if use_llm else ({}, {"error": "LLM off"})
        tr.step(f"map {side} columns", t, "asked", missing=need, llm_suggestion=suggestion,
                llm_ms=meta.get("ms"), llm_error=meta.get("error"), rejected=meta.get("rejected"))
        return {"type": "column_mapping", "side": side, "missing": need, "headers": headers,
                "sample": [dict(zip(headers, r)) for r in rows[:3]], "found": found,
                "suggested": suggestion, "suggestion_reason": meta.get("reason"),
                "text": f"Which column in the {side} file holds the {' and the '.join(need)}?"}
    tr.step(f"map {side} columns", t, mapping=found, how=how)
    return headers, rows, found, how


def _date_answer(answers: dict, side: str) -> str | None:
    v = answers.get("date_format")
    v = v.get(side) if isinstance(v, dict) else None
    return v if v in {"dmy", "mdy", "ymd"} else None


def _type_as_flag(found: dict, headers: list[str], rows: list[list[str]]) -> None:
    if "type" in found and "dc_flag" not in found:
        vals = {r[headers.index(found["type"])].strip().lower() for r in rows} - {""}
        if vals and vals <= (DEBIT_WORDS | CREDIT_WORDS):
            found["dc_flag"] = found.pop("type")


def _run(bank_csv, ledger_csv, answers, use_llm, tr) -> dict:
    parsed = {}
    for side, data in (("bank", bank_csv), ("ledger", ledger_csv)):
        got = _understand(side, data, answers, use_llm, tr)
        if isinstance(got, dict):
            return {"status": "needs_input", "questions": [got]}
        parsed[side] = got
    orders = {}
    for side, (headers, rows, found, _) in parsed.items():
        t = time.perf_counter()
        order, why = resolve_order(headers, rows, found, _date_answer(answers, side))
        if not order:
            tr.step(f"read {side} dates", t, "asked", reason=why)
            return {"status": "needs_input", "questions": [{
                "type": "date_format", "side": side, "column": found["date"],
                "examples": [r[headers.index(found["date"])] for r in rows[:4]],
                "text": f"Are the {side} dates day-first (31/01) or month-first (01/31)? No row settles it."}]}
        orders[side] = order
        tr.step(f"read {side} dates", t, order=order, decided_by=why)
    return _reconcile(parsed, orders, answers, tr, use_llm)


def _sheets(parsed, orders, tr) -> dict[str, Sheet]:
    t = time.perf_counter()
    sheets = {s: build(s, *parsed[s][:2], parsed[s][2], parsed[s][3], orders[s], None) for s in parsed}
    cur = {s: {x.currency for x in sh.txns} for s, sh in sheets.items()}
    for s, other in (("bank", "ledger"), ("ledger", "bank")):
        if cur[s] == {"UNSPECIFIED"} and len(cur[other]) == 1 and cur[other] != {"UNSPECIFIED"}:
            code = next(iter(cur[other]))
            sheets[s] = build(s, *parsed[s][:2], parsed[s][2], parsed[s][3], orders[s], code)
            sheets[s].currency_source = f"assumed {code}: {other} file is single-currency {code}"
    for s, sh in sheets.items():
        if not sh.txns:
            raise InputError(f"{s} file: no row had a readable date and amount ({len(sh.bad_rows)} rows failed)")
    tr.step("normalise transactions", t, bank=len(sheets["bank"].txns), ledger=len(sheets["ledger"].txns),
            unreadable_rows=sum(len(sh.bad_rows) for sh in sheets.values()),
            currency={s: sh.currency_source for s, sh in sheets.items()})
    return sheets


def _fix_ledger_sign(sheets, tr) -> None:
    """Ledger exports disagree on sign. Keep the convention that agrees with the bank on the most amounts."""
    t = time.perf_counter()
    bank = Counter((x.currency, x.amount) for x in sheets["bank"].txns)
    led = sheets["ledger"].txns
    options = {"as exported": [x.amount for x in led], "flipped": [-x.amount for x in led]}
    if all(x.amount > 0 for x in led) and any(payable_kind(x) for x in led):
        options["payables negative (Type column)"] = [-x.amount if payable_kind(x) else x.amount for x in led]
    score = {k: sum(min(bank[(x.currency, a)], 1) for x, a in zip(led, v)) for k, v in options.items()}
    # Change the export's signs only on clear evidence: one misread minus must not flip a whole ledger.
    best = max(score, key=lambda k: (score[k], k == "as exported"))
    if best != "as exported" and not (score[best] >= 3 and score[best] >= 2 * score["as exported"]):
        best = "as exported"
    for x, a in zip(led, options[best]):
        x.amount = a
    tr.step("choose ledger sign", t, chosen=best, agreeing_amounts=score)


def _list(v) -> list:
    return v if isinstance(v, list) else []


def _rows(v) -> list[int]:
    return [int(x) for x in (v if isinstance(v, list) else [v]) if isinstance(x, int) or str(x).isdigit()]


def _reconcile(parsed, orders, answers, tr, use_llm: bool) -> dict:
    sheets = _sheets(parsed, orders, tr)
    _fix_ledger_sign(sheets, tr)
    bank, ledger = sheets["bank"].txns, sheets["ledger"].txns
    t = time.perf_counter()
    forced = [(_rows(p.get("bank")), _rows(p.get("ledger"))) for p in _list(answers.get("pairs")) if isinstance(p, dict)]
    res, dups = reconcile.run(bank, ledger, forced)
    if time.perf_counter() - t > MATCH_BUDGET_S:
        raise InputError(f"Matching took over {MATCH_BUDGET_S:.0f} s; split the files into smaller periods.")
    rules = Counter(m.rule for m in res.matches)
    tr.step("match", t, matched=len(res.matches), by_rule=dict(rules), mismatches=len(res.mismatches),
            duplicates=len(dups), held_for_question=len(res.held), answers_not_applied=res.notes or None)
    t = time.perf_counter()
    excs = reconcile.exceptions(bank, ledger, res, dups, {s: sh.bad_rows for s, sh in sheets.items()})
    as_of = max(x.date for x in bank)
    fus = reconcile.followups(ledger, excs, as_of)
    tr.step("classify exceptions", t, exceptions=len(excs), followups=len(fus), as_of=as_of.isoformat())
    t = time.perf_counter()
    meta = narrate(excs, fus, use_llm)
    tr.step("explain + draft (LLM, numbers checked)", t, "ok" if not meta["exceptions_call"].get("error") else "fallback",
            **meta)
    questions = [{"type": "ambiguous_match", **a, "text": f"Which lines belong together? {a['why'].capitalize()}."}
                 for a in res.ambiguous]
    return {"status": "needs_input" if questions else "done", "questions": questions,
            "totals": reconcile.totals(bank, ledger, res),
            "overview": reconcile.overview(bank, ledger, res, excs, fus, len(questions)),
            "matches": [reconcile.summary(m) for m in res.matches], "exceptions": excs, "followups": fus,
            "unreadable_rows": {s: sh.bad_rows for s, sh in sheets.items()},
            "columns": {s: {"mapping": sh.mapping, "how": sh.how, "date_order": sh.date_order,
                            "currency": sh.currency_source} for s, sh in sheets.items()}}
