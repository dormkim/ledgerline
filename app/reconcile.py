"""Duplicates, exceptions with evidence cards, per-currency totals. All numbers come from here, not the LLM."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from .matcher import Link, Result, match_all
from .reader import Txn
from .textmatch import refs, tokens

DEFAULT_TERMS_DAYS = 30


def find_duplicates(bank: list[Txn]) -> list[tuple[Txn, Txn]]:
    seen: dict[tuple, Txn] = {}
    dups = []
    for t in bank:
        # References are part of the key: 'ACME INV-1042' and 'ACME INV-1043' are two payments, not one twice.
        key = (t.date, t.amount, t.currency, " ".join(sorted(tokens(t.text))) or t.text.lower(), tuple(sorted(refs(t.text))))
        if key in seen:
            dups.append((t, seen[key]))
        else:
            seen[key] = t
    return dups


def run(bank: list[Txn], ledger: list[Txn], forced=None) -> tuple[Result, list[tuple[Txn, Txn]]]:
    """Match everything first; a repeated bank line that found no ledger line of its own is a suspected duplicate.

    (Setting repeats aside before matching flagged two genuine, identical rent payments as duplicates.)
    """
    res = match_all(bank, ledger, forced)
    used = {t.row for m in res.matches + res.mismatches for t in m.bank} | {r for s, r in res.held if s == "b"}
    return res, [(d, o) for d, o in find_duplicates(bank) if d.row not in used]


def exceptions(bank, ledger, res: Result, dups, unreadable: dict | None = None) -> list[dict]:
    out: list[dict] = []
    for side, rows in (unreadable or {}).items():  # shown, never silently dropped
        for r in rows:
            out.append({"kind": "unreadable_row", "rule": r["reason"], "bank": [], "ledger": [],
                        side: [{"side": side, "row": r["row"], "raw": r["raw"]}], "facts": {"row": r["row"]},
                        "hint": "Fix the row in the export (or answer the column question) and re-run."})
    for m in res.mismatches:
        bank_amt, ledger_amt = sum(t.amount for t in m.bank), sum(t.amount for t in m.ledger)
        out.append(_exc("amount_mismatch", m.bank, m.ledger, m.rule, m.evidence | {
            "bank_amount": str(bank_amt), "ledger_amount": str(ledger_amt), "currency": m.bank[0].currency},
            _mismatch_hint(bank_amt, ledger_amt)))
    for d, orig in dups:
        out.append(_exc("possible_duplicate", [d, orig], [], "same date, amount and text as an earlier bank line",
                         {"duplicate_of_row": orig.row, "amount": str(d.amount), "currency": d.currency},
                         "Check with the bank whether this was charged twice before booking it."))
    done_b = {t.row for m in res.matches + res.mismatches for t in m.bank} | {d.row for d, _ in dups}
    done_l = {t.row for m in res.matches + res.mismatches for t in m.ledger}
    held_b = {r for s, r in res.held if s == "b"}
    held_l = {r for s, r in res.held if s == "l"}
    for t in bank:
        if t.row not in done_b and t.row not in held_b:
            out.append(_exc("unmatched_bank", [t], [], "no ledger line with this amount within the window",
                            {"amount": str(t.amount), "currency": t.currency},
                            "Book it in the ledger, or find the invoice it pays."))
    for t in ledger:
        if t.row not in done_l and t.row not in held_l:
            out.append(_exc("unmatched_ledger", [], [t], "no bank line with this amount within the window",
                            {"amount": str(t.amount), "currency": t.currency},
                            "Not yet paid, or paid into another account." if t.amount > 0
                            else "Payment not yet cleared, or paid from another account."))
    for i, e in enumerate(out, start=1):
        e["id"] = f"E{i}"
    return out


def _exc(kind, bank, ledger, rule, facts, hint) -> dict:
    return {"kind": kind, "rule": rule, "bank": [t.card() for t in bank], "ledger": [t.card() for t in ledger],
            "facts": facts, "hint": hint}


def _mismatch_hint(bank_amt: Decimal, ledger_amt: Decimal) -> str:
    if abs(bank_amt) < abs(ledger_amt):
        return ("Received less than invoiced: likely a bank/transfer fee or a short payment. "
                "Book the difference as a fee or ask the payer.")
    return "Received more than invoiced: overpayment, or the payment also covers another invoice."


def totals(bank: list[Txn], ledger: list[Txn], res: Result) -> dict:
    t: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for side, rows in (("bank", bank), ("ledger", ledger)):
        for x in rows:
            t[x.currency][f"{side}_{'in' if x.amount > 0 else 'out'}"] += x.amount
            t[x.currency][f"{side}_net"] += x.amount
    for m in res.matches:
        for x in m.bank:
            t[x.currency]["matched_bank"] += x.amount
    for cur in t:
        t[cur]["net_difference"] = t[cur]["bank_net"] - t[cur]["ledger_net"]
    keys = ["bank_in", "bank_out", "bank_net", "ledger_in", "ledger_out", "ledger_net", "matched_bank", "net_difference"]
    return {cur: {k: str(v.get(k, Decimal("0"))) for k in keys} for cur, v in sorted(t.items())}


def followups(ledger: list[Txn], excs: list[dict], as_of: date) -> list[dict]:
    """Receivables still unpaid after their due date (due column, else invoice date + 30 days)."""
    out = []
    unmatched = {e["ledger"][0]["row"]: e["id"] for e in excs if e["kind"] == "unmatched_ledger"}
    for t in ledger:
        if t.row not in unmatched or t.amount <= 0:
            continue
        due = t.due or (t.date + timedelta(days=DEFAULT_TERMS_DAYS))
        late = (as_of - due).days
        if late > 0:
            out.append({"id": f"F{len(out) + 1}", "exception": unmatched[t.row], "ledger_row": t.row,
                        "counterparty": t.name or t.desc, "ref": t.ref, "amount": str(t.amount), "currency": t.currency,
                        "due": due.isoformat(), "due_source": "due column" if t.due else f"invoice date + {DEFAULT_TERMS_DAYS} days",
                        "days_overdue": late, "as_of": as_of.isoformat(), "status": "draft"})
    return out


def summary(link: Link) -> dict:
    return {"rule": link.rule, "bank": [t.card() for t in link.bank], "ledger": [t.card() for t in link.ledger],
            "evidence": link.evidence}
