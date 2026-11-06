"""Find which column is the date, the amount, the counterparty… from headers first, values second.

The result says how each role was found ('header', 'values', 'running-balance', 'llm', 'user') so the
UI can show it. If date or money cannot be pinned down we return None and the pipeline asks the user.
"""
from __future__ import annotations

import re

from .values import date_order, money_style, parse_date, parse_money

# Patterns are matched against the lower-cased header with punctuation turned into spaces.
ROLE_PATTERNS: dict[str, list[str]] = {
    "due": [r"\bdue\b", r"f[aä]llig"],
    "date": [r"^date$", r"transaction date", r"posting date", r"^posted", r"booking date", r"buchungs?tag",
             r"^datum$", r"txn date", r"trans date", r"invoice date", r"bill date", r"^date\b", r"\bdate$",
             r"value date", r"valuta", r"wertstellung", r"^fecha", r"^date "],
    "in": [r"money in", r"paid in", r"deposit", r"^in$", r"inflow", r"receipt", r"received", r"eingang", r"^income",
           r"credit amount", r"gutschrift"],
    "out": [r"money out", r"paid out", r"withdrawal", r"^out$", r"outflow", r"payment amount", r"ausgang",
            r"debit amount", r"lastschrift", r"spent", r"^payments?\b", r"^paid$", r"^expenses?\b"],
    "debit": [r"^debit$", r"^dr$", r"^soll$", r"^debe$"],
    "credit": [r"^credit$", r"^cr$", r"^haben$", r"^haber$"],
    "amount": [r"^amount\b", r"\bamount$", r"\bamt\b", r"betrag", r"umsatz", r"montant", r"importe",
               r"^value$", r"^total$", r"^sum$", r"^gross", r"^net amount"],
    "dc_flag": [r"^dr ?cr$", r"^d ?c$", r"debit ?credit", r"^s ?h$", r"soll ?haben", r"^cr ?dr$"],
    "currency": [r"currency", r"^ccy$", r"^cur$", r"w[aä]hrung", r"waehrung", r"devise", r"moneda"],
    "ref": [r"invoice (no|number|num|#)", r"^inv", r"^ref", r"reference", r"^num$", r"^no$", r"doc(ument)? ?(no|number)?$",
            r"check ?(no|number)", r"bill (no|number)", r"rechnungs?nr", r"belegnr", r"transaction id",
            r"^n pi[eè]ce", r"^n[uú]m[eé]ro", r"^n[uú]m\b", r"factura", r"facture", r"^pi[eè]ce$"],
    "name": [r"payee", r"payer", r"counterpart", r"^name$", r"customer", r"vendor", r"supplier", r"^contact",
             r"beneficiary", r"merchant", r"empf[aä]nger", r"auftraggeber", r"beg[uü]nstigter", r"zahlungspflichtiger",
             r"^party", r"client", r"^tiers$", r"tercero", r"proveedor", r"fournisseur", r"raz[oó]n social"],
    "desc": [r"description", r"details", r"^memo", r"narrative", r"^text$", r"verwendungszweck", r"buchungstext",
             r"particulars", r"^note", r"concept", r"\bdesc", r"narration", r"^payee details", r"libell[eé]"],
    "type": [r"^type$", r"transaction type", r"^kind$", r"^category$"],
}
BLOCK_MONEY = re.compile(r"balance|saldo|running|tax|vat|qty|quantity|rate|price|unit")


def norm(h: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w#]+", " ", h.lower())).strip()


def from_headers(headers: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    used: set[str] = set()
    for role, pats in ROLE_PATTERNS.items():
        for pat in pats:
            hit = next((h for h in headers if h not in used and re.search(pat, norm(h))), None)
            if hit and not (role in {"amount", "in", "out", "debit", "credit"} and BLOCK_MONEY.search(norm(hit))):
                found[role] = hit
                used.add(hit)
                break
    return found


def column(rows: list[list[str]], headers: list[str], name: str) -> list[str]:
    i = headers.index(name)
    return [r[i] for r in rows]


def date_rate(values: list[str]) -> float:
    order = date_order(values) or "dmy"
    ok = sum(parse_date(v, order) is not None for v in values if v.strip())
    filled = sum(1 for v in values if v.strip())
    return ok / filled if filled else 0.0


def money_rate(values: list[str]) -> float:
    style = money_style(values)
    filled = [v for v in values if v.strip()]
    if not filled:
        return 0.0
    ok = sum(parse_money(v, style) is not None and not _looks_like_date(v) for v in filled)
    return ok / len(filled)


def _looks_like_date(v: str) -> bool:
    return bool(re.match(r"^\s*\d{1,4}[./-]\d{1,2}[./-]\d{1,4}\s*$", v))


def from_values(headers: list[str], rows: list[list[str]], found: dict[str, str]) -> dict[str, str]:
    """Fill date/amount only when exactly one column qualifies — otherwise leave it for a question."""
    out = dict(found)
    free = [h for h in headers if h not in out.values()]
    if "date" not in out:
        dates = [h for h in free if date_rate(column(rows, headers, h)) >= 0.9]
        if len(dates) == 1:
            out["date"] = dates[0]
    if not has_money(out):
        nums = [h for h in free if h != out.get("date") and money_rate(column(rows, headers, h)) >= 0.9
                and _has_decimals(column(rows, headers, h))]
        nums = _drop_running_balance(headers, rows, nums)
        if len(nums) == 1:
            out["amount"] = nums[0]
    if "name" not in out and "desc" not in out:  # without any text we lose all name/reference evidence
        texts = [h for h in free if h not in out.values()
                 and sum(bool(re.search(r"[A-Za-z]{3}", v)) for v in column(rows, headers, h)) >= 0.7 * len(rows)]
        if texts:
            out["desc"] = texts[0]
    return out


def has_money(found: dict[str, str]) -> bool:
    return "amount" in found or ({"in", "out"} <= found.keys()) or ({"debit", "credit"} <= found.keys())


def _has_decimals(values: list[str]) -> bool:
    return any(re.search(r"[.,]\d{2}\b", v) for v in values)


def _drop_running_balance(headers, rows, cols: list[str]) -> list[str]:
    """If column B equals the running sum of column A, B is a balance, not an amount."""
    if len(cols) != 2:
        return cols
    a, b = ([parse_money(v, money_style(column(rows, headers, c))) for v in column(rows, headers, c)] for c in cols)
    for amt, bal, drop in ((a, b, cols[1]), (b, a, cols[0])):
        if None in amt or None in bal or len(amt) < 3:
            continue
        if all(bal[i] - bal[i - 1] == amt[i] for i in range(1, len(amt))) or \
           all(bal[i - 1] - bal[i] == amt[i - 1] for i in range(1, len(amt))):
            return [c for c in cols if c != drop]
    return cols


def missing(found: dict[str, str]) -> list[str]:
    need = []
    if "date" not in found:
        need.append("date")
    if not has_money(found):
        need.append("amount")
    return need
