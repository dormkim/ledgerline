"""One CSV a bookkeeper can open in Excel: every match, exception and follow-up of a run, one line each.

Numbers are copied as the code computed them (strings from Decimal). Text cells that a spreadsheet would
run as a formula are prefixed with an apostrophe (CSV injection), but signed amounts are left as numbers.
"""
from __future__ import annotations

import csv
import io
import re
from decimal import Decimal

COLUMNS = ["section", "id", "kind_or_rule", "currency", "bank_rows", "ledger_rows", "bank_amount",
           "ledger_amount", "difference", "counterparty", "detail", "next_step", "status"]
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def _safe(v) -> str:
    s = "" if v is None else str(v)
    if s and s[0] in "=+-@\t\r" and not _NUMBER.match(s):
        return "'" + s
    return s


def _rows(lines: list[dict]) -> str:
    return " ".join(str(t["row"]) for t in lines)


def _sum(lines: list[dict]) -> str:
    return str(sum((Decimal(t["amount"]) for t in lines if "amount" in t), Decimal("0"))) if lines else ""


def _party(lines: list[dict]) -> str:
    return next((t.get("name") or t.get("desc") or "" for t in lines if "row" in t and "raw" not in t), "")


def records(run: dict) -> list[list]:
    out = []
    for m in run.get("matches", []):
        cur = (m["bank"] or m["ledger"])[0]["currency"]
        out.append(["match", "", m["rule"], cur, _rows(m["bank"]), _rows(m["ledger"]), _sum(m["bank"]),
                    _sum(m["ledger"]), "0", _party(m["ledger"]) or _party(m["bank"]), "", "", "matched"])
    for e in run.get("exceptions", []):
        f, n = e.get("facts", {}), e.get("narrative", {})
        out.append(["exception", e["id"], e["kind"], f.get("currency", ""), _rows(e["bank"]), _rows(e["ledger"]),
                    f.get("bank_amount") or (_sum(e["bank"]) if e["bank"] and "raw" not in e["bank"][0] else ""),
                    f.get("ledger_amount") or (_sum(e["ledger"]) if e["ledger"] and "raw" not in e["ledger"][0] else ""),
                    f.get("difference", ""), _party(e["ledger"]) or _party(e["bank"]),
                    n.get("text", ""), n.get("next_step", e.get("hint", "")), "to review"])
    for x in run.get("followups", []):
        out.append(["follow-up", x["id"], f"{x['days_overdue']} days overdue (due {x['due']})", x["currency"], "",
                    str(x["ledger_row"]), "", x["amount"], "", x["counterparty"],
                    (x.get("draft") or {}).get("subject", ""), "approve reminder", x.get("status", "")])
    for q in run.get("questions", []):
        out.append(["question", "", q.get("type", ""), q.get("currency", ""), " ".join(map(str, q.get("bank", []))),
                    " ".join(map(str, q.get("ledger", []))), "", "", "", "", q.get("text", ""), "answer in the app", "open"])
    return out


def to_csv(run: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for r in records(run):
        w.writerow([_safe(v) for v in r])
    return "﻿" + buf.getvalue()  # BOM: Excel opens UTF-8 names (Zahnarztpraxis, Bürohaus) correctly
