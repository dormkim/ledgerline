"""Ask the LLM which column is which — only when header rules and value checks could not tell.

The proposal is accepted only if code confirms it: the date column must parse as dates and the
amount column(s) as money for at least 90% of rows. Otherwise the user gets the question.
"""
from __future__ import annotations

import json

from . import llm
from .columns import column, date_rate, money_rate

SYSTEM = """You map columns of a CSV export (bank statement or accounting ledger) to roles.
Roles: date, amount (single signed amount), in / out (separate money-in and money-out columns),
debit / credit, currency, name (counterparty), ref (invoice/reference number), desc (free text), due.
Use only header names that exist. Omit roles you are not sure about.
Reply with JSON only: {"mapping": {"date": "<header>", "amount": "<header>", ...}, "reason": "<one sentence>"}"""


def propose(side: str, headers: list[str], rows: list[list[str]], found: dict[str, str]) -> tuple[dict, dict]:
    sample = [dict(zip(headers, r)) for r in rows[:6]]
    user = json.dumps({"file": side, "headers": headers, "sample_rows": sample, "already_known": found})
    reply, meta = llm.chat_json(SYSTEM, user, max_tokens=400, timeout=30)
    if not reply:
        return {}, meta
    proposal = {k: v for k, v in (reply.get("mapping") or {}).items() if isinstance(v, str) and v in headers}
    accepted, rejected = {}, []
    for role, h in proposal.items():
        if role in found:
            continue
        vals = column(rows, headers, h)
        if role in {"date", "due"} and date_rate(vals) < 0.9:
            rejected.append(f"{role}='{h}' (values are not dates)")
        elif role in {"amount", "in", "out", "debit", "credit"} and money_rate(vals) < 0.9:
            rejected.append(f"{role}='{h}' (values are not amounts)")
        else:
            accepted[role] = h
    meta["reason"] = str(reply.get("reason", ""))[:200]
    meta["rejected"] = rejected
    return accepted, meta
