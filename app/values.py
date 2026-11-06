"""Parse money and dates the way real exports write them.

Money is always Decimal (never float) and never rounded. A value we cannot read
returns None so the caller can count it as a parse failure instead of a zero.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# "$" is deliberately absent: USD, CAD, AUD… all use it, so it does not tell us the currency.
CURRENCY_SYMBOLS = {"€": "EUR", "£": "GBP", "¥": "JPY", "₩": "KRW", "₹": "INR"}
_ISO_CODE = re.compile(r"\b([A-Z]{3})\b")
# Only real currency codes count ("Amt", "Sum", "Net" in a header must not become currencies).
ISO_CODES = set("""USD EUR GBP JPY CNY KRW INR CAD AUD NZD CHF SEK NOK DKK PLN CZK HUF RON BGN HKD SGD TWD THB
MYR IDR PHP VND MXN BRL ARS CLP COP PEN ZAR NGN KES EGP AED SAR QAR KWD BHD OMR ILS TRY RUB UAH ISK""".split())
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def money_style(values: list[str]) -> str:
    """'comma' if the column writes decimals with a comma (1.234,56 or 12,50), else 'dot'.

    A whole-number column like '1.500', '2.000' uses the dot for thousands, so it is 'comma' style too.
    """
    filled = [re.sub(r"[^\d.,]", "", v or "") for v in values if (v or "").strip()]
    if filled and all(re.fullmatch(r"\d{1,3}(\.\d{3})+|\d{1,3}", f) for f in filled) and any("." in f for f in filled):
        return "comma"
    comma = dot = 0
    for v in values:
        s = re.sub(r"[^\d.,]", "", v or "")
        if re.search(r",\d{1,2}$", s) and not re.search(r"\.\d{1,2}$", s):
            comma += 1
        elif re.search(r"\.\d{1,2}$", s):
            dot += 1
    return "comma" if comma > dot else "dot"


def parse_money(raw: str, style: str = "dot") -> Decimal | None:
    s = (raw or "").strip().replace("\u2212", "-")  # Unicode minus from PDF-to-CSV tools
    if not s:
        return None
    if len(re.sub(r"\D", "", s)) > 18:
        return None
    # '-' anywhere before the first digit ('$-20.00', 'USD -12.50'), a trailing '-', or (brackets)
    neg = bool(re.match(r"^[^\d]*-", s)) or s.endswith("-") or (s.startswith("(") and s.endswith(")"))
    upper = s.upper()
    if re.search(r"\b(DR|DEBIT)\b$", upper):
        neg = True
    digits = re.sub(r"[^\d.,]", "", s)
    if not re.search(r"\d", digits):
        return None
    if style == "comma":
        digits = digits.replace(".", "").replace(",", ".")
    else:
        digits = digits.replace(",", "")
    if digits.count(".") > 1:  # 1.234.567 in a dot-style column means thousands
        head, _, tail = digits.rpartition(".")
        digits = head.replace(".", "") + ("." + tail if len(tail) <= 2 else tail)
    try:
        value = Decimal(digits)
    except InvalidOperation:
        return None
    return -value if neg else value


def currency_hint(raw: str) -> str | None:
    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in (raw or ""):
            return code
    codes = [c for c in _ISO_CODE.findall((raw or "").upper()) if c in ISO_CODES]
    return codes[0] if codes else None


def _parts(raw: str) -> tuple[str, list[str]] | None:
    s = (raw or "").strip().split("T")[0].split(" ")[0] if re.match(r"^\d", (raw or "").strip()) else (raw or "").strip()
    for sep in "-/.":
        bits = s.split(sep)
        if len(bits) == 3 and all(b.isdigit() and len(b) <= 4 for b in bits):
            return sep, bits
    return None


def date_order(values: list[str]) -> str | None:
    """Decide 'ymd', 'dmy' or 'mdy' for a whole column. None means the column itself cannot tell."""
    seen = [p[1] for p in (_parts(v) for v in values) if p]
    if not seen:
        return "text"
    if all(len(b[0]) == 4 for b in seen):
        return "ymd"
    first = max(int(b[0]) for b in seen)
    second = max(int(b[1]) for b in seen)
    if first > 12 and second <= 12:
        return "dmy"
    if second > 12 and first <= 12:
        return "mdy"
    if all(p[0] == "." for p in (_parts(v) for v in values) if p):
        return "dmy"  # dotted dates (31.01.2026) are day-first in every locale that uses them
    return None


def parse_date(raw: str, order: str | None) -> date | None:
    s = (raw or "").strip()
    if not s:
        return None
    p = _parts(s)
    if p and order in {"ymd", "dmy", "mdy"}:
        a, b, c = (int(x) for x in p[1])
        y, m, d = {"ymd": (a, b, c), "dmy": (c, b, a), "mdy": (c, a, b)}[order]
        if y < 100:
            y += 2000
        try:
            return date(y, m, d)
        except (ValueError, OverflowError):
            return None
    m = re.match(r"^(\d{1,2})[\s-]([A-Za-z]{3})[a-z]*[\s,-]+(\d{2,4})", s) or None
    if m:
        d, mon, y = int(m.group(1)), _MONTHS.get(m.group(2).lower()), int(m.group(3))
    else:
        m = re.match(r"^([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s)
        if not m:
            return _iso_fallback(s)
        mon, d, y = _MONTHS.get(m.group(1).lower()), int(m.group(2)), int(m.group(3))
    if not mon:
        return None
    try:
        return date(y + 2000 if y < 100 else y, mon, d)
    except (ValueError, OverflowError):
        return None


def _iso_fallback(s: str) -> date | None:
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None
