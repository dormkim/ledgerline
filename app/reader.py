"""Turn mapped rows into transactions. Every row keeps its line number and raw cells for the evidence card."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .columns import column
from .values import currency_hint, date_order, money_style, parse_date, parse_money

DEBIT_WORDS = {"d", "dr", "debit", "s", "soll", "debe", "withdrawal", "out"}
CREDIT_WORDS = {"c", "cr", "credit", "h", "haben", "haber", "deposit", "in"}
PAYABLE_WORDS = re.compile(r"bill|expense|payable|purchase|vendor|supplier|payment made|check|cheque|refund issued")


@dataclass
class Txn:
    side: str            # "bank" or "ledger"
    row: int             # 1-based data row, header excluded
    date: date
    amount: Decimal      # signed: money in > 0, money out < 0
    currency: str
    name: str
    ref: str
    desc: str
    due: date | None
    raw: dict[str, str] = field(repr=False)
    kind: str = ""       # value of a Type column, used only to guess payables

    @property
    def text(self) -> str:
        return " ".join(x for x in (self.name, self.ref, self.desc) if x)

    def card(self) -> dict:
        return {"side": self.side, "row": self.row, "date": self.date.isoformat(), "amount": str(self.amount),
                "currency": self.currency, "name": self.name, "ref": self.ref, "desc": self.desc}


@dataclass
class Sheet:
    side: str
    headers: list[str]
    mapping: dict[str, str]
    how: dict[str, str]
    date_order: str
    txns: list[Txn]
    bad_rows: list[dict]      # rows we could not read, with the reason
    currency_source: str


def _cell(row: list[str], headers: list[str], name: str | None) -> str:
    return row[headers.index(name)].strip() if name else ""


def file_currency(headers: list[str], rows: list[list[str]], mapping: dict[str, str]) -> tuple[str | None, str]:
    for h in (mapping.get("amount"), mapping.get("in"), mapping.get("debit")):
        if h and (code := currency_hint(h.upper())):
            return code, f"header '{h}'"
    money_cols = [mapping[k] for k in ("amount", "in", "out", "debit", "credit") if k in mapping]
    hints = {currency_hint(v) for h in money_cols for v in column(rows, headers, h)} - {None}
    if len(hints) == 1:
        return hints.pop(), "symbol in amounts"
    return None, "not stated"


def build(side: str, headers: list[str], rows: list[list[str]], mapping: dict[str, str], how: dict[str, str],
          order: str, fallback_currency: str | None) -> Sheet:
    cur, cur_src = file_currency(headers, rows, mapping)
    cur = cur or fallback_currency or "UNSPECIFIED"
    if "currency" in mapping:
        cur_src = f"column '{mapping['currency']}'"
    styles = {k: money_style(column(rows, headers, mapping[k]))
              for k in ("amount", "in", "out", "debit", "credit") if k in mapping}
    txns, bad = [], []
    for i, r in enumerate(rows, start=1):
        raw = dict(zip(headers, r))
        d = parse_date(_cell(r, headers, mapping.get("date")), order)
        amt = _amount(side, r, headers, mapping, styles)
        if d is None or amt is None:
            bad.append({"row": i, "reason": "date unreadable" if d is None else "amount unreadable", "raw": raw})
            continue
        row_cur = _row_currency(_cell(r, headers, mapping.get("currency")), cur) if "currency" in mapping else cur
        due = parse_date(_cell(r, headers, mapping.get("due")), order) if "due" in mapping else None
        txns.append(Txn(side, i, d, amt, row_cur, _cell(r, headers, mapping.get("name")),
                        _cell(r, headers, mapping.get("ref")), _cell(r, headers, mapping.get("desc")), due, raw,
                        _cell(r, headers, mapping.get("type"))))
    return Sheet(side, headers, mapping, how, order, txns, bad, cur_src)


def _row_currency(cell: str, default: str) -> str:
    """'€' or 'eur' in a currency column → 'EUR'. Unknown text is kept as written, so it never matches by accident."""
    return currency_hint(cell) or cell.strip().upper() or default


def _amount(side, r, headers, mapping, styles) -> Decimal | None:
    get = lambda k: parse_money(_cell(r, headers, mapping.get(k)), styles.get(k, "dot"))  # noqa: E731
    if "amount" in mapping:
        v = get("amount")
        if v is None:
            return None
        flag = _cell(r, headers, mapping.get("dc_flag")).lower()
        if flag in DEBIT_WORDS:
            v = -abs(v) if side == "bank" else abs(v)
        elif flag in CREDIT_WORDS:
            v = abs(v) if side == "bank" else -abs(v)
        return v
    pair = ("in", "out") if "in" in mapping else ("credit", "debit")
    if side == "ledger" and pair == ("credit", "debit"):
        pair = ("debit", "credit")  # cash book: a debit raises cash. Sign resolution can still flip it.
    cells = {k: _cell(r, headers, mapping.get(k)) for k in pair}
    pos, neg = get(pair[0]), get(pair[1])
    if (cells[pair[0]] and pos is None) or (cells[pair[1]] and neg is None) or (pos is None and neg is None):
        return None  # a filled cell we cannot read is unreadable, never a silent 0
    # Keep a sign the export already wrote: 'Paid in = -75.00' is a reversal, not a +75 receipt.
    return (pos or 0) - abs(neg or 0)


def resolve_order(headers, rows, mapping, chosen: str | None = None) -> tuple[str | None, str]:
    """Day-first vs month-first. The column decides; if it cannot, sorted order decides; else we ask."""
    if chosen:
        return chosen, "user"
    if "date" not in mapping:
        return None, "no date column"
    values = column(rows, headers, mapping["date"])
    order = date_order(values)
    if order:
        return order, "values"
    sorted_ok = {o: _monotonic([parse_date(v, o) for v in values]) for o in ("dmy", "mdy")}
    if sorted_ok["dmy"] != sorted_ok["mdy"]:
        return ("dmy" if sorted_ok["dmy"] else "mdy"), "row order"
    return None, "ambiguous"


def _monotonic(ds: list) -> bool:
    ds = [d for d in ds if d]
    return len(ds) >= 2 and (all(a <= b for a, b in zip(ds, ds[1:])) or all(a >= b for a, b in zip(ds, ds[1:])))


def payable_kind(t: Txn) -> bool:
    return bool(PAYABLE_WORDS.search(t.kind.lower()))
