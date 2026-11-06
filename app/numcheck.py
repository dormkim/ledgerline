"""Every number the LLM writes must already exist in the evidence it was given, in the right role.

- A number next to a currency ('1,042 EUR', '$30') must be one of the evidence's money values.
- A percentage is allowed only if the evidence itself says it ('3% Skonto' in a bank text); any other
  '%' is the model doing arithmetic.
- Other numbers (days, row numbers, dates, invoice numbers) must appear as a whole value in the evidence.
Sentences that break a rule are removed and reported; the LLM may phrase things, not compute them.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .values import ISO_CODES

NUM = re.compile(r"\d[\d,.]*\d|\d")
_CODES = "|".join(sorted(ISO_CODES))
CURRENCY_NEAR = re.compile(rf"([$€£¥₩]|\b(?:{_CODES})\b)\s*-?$|^\s*(\b(?:{_CODES})\b|[$€£¥₩])")
# Fields that are prose or internal scores, not facts the text may quote numbers from.
SKIP_KEYS = {"due_source", "rule", "hint", "why", "name_score", "status", "id", "exception", "basis", "note"}
MONEY_KEYS = re.compile(r"amount|difference|sum")
ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _norms(token: str) -> set[Decimal]:
    out = set()
    candidates = {token.replace(",", "")}
    if re.search(r",\d{1,2}$", token):
        candidates.add(token.replace(".", "").replace(",", "."))
    for c in candidates:
        try:
            out.add(abs(Decimal(c.rstrip("."))).normalize())
        except InvalidOperation:
            pass
    return out


def _walk(x, key: str, out: set, money: set, pct: set) -> None:
    if key in SKIP_KEYS:
        return
    if isinstance(x, dict):
        for k, v in x.items():
            _walk(v, str(k), out, money, pct)
    elif isinstance(x, (list, tuple, set)):
        for v in x:
            _walk(v, key, out, money, pct)
    elif x is not None and not isinstance(x, bool):
        s = str(x)
        m = ISO_DATE.match(s)
        if m:  # '2026-10-05' may be written 'October 5, 2026' or '05/10/2026'
            out.update(Decimal(p).normalize() for p in m.groups())
            return
        for p in re.findall(r"(\d[\d,.]*)\s*%", s):
            pct.update(_norms(p))
        for tok in NUM.findall(s):
            vals = _norms(tok)
            out.update(vals)
            if MONEY_KEYS.search(key):
                money.update(vals)


def evidence(*facts) -> tuple[set[Decimal], set[Decimal], set[Decimal]]:
    """(all allowed numbers, allowed money values, percentages the evidence itself states)."""
    out: set[Decimal] = set()
    money: set[Decimal] = set()
    pct: set[Decimal] = set()
    for f in facts:
        _walk(f, "", out, money, pct)
    return out, money, pct


def allowed_numbers(*facts) -> set[Decimal]:
    return evidence(*facts)[0]


def bad_numbers(text: str, allowed: set[Decimal], money: set[Decimal] | None = None,
                pct: set[Decimal] | None = None) -> list[str]:
    bad = []
    text = text or ""
    for m in NUM.finditer(text):
        tok, vals = m.group(), _norms(m.group())
        before, after = text[max(0, m.start() - 5):m.start()], text[m.end():m.end() + 5]
        if after.lstrip().startswith("%"):
            if not (vals & (pct or set())):
                bad.append(tok)
        elif not (vals & allowed):
            bad.append(tok)
        elif money is not None and (CURRENCY_NEAR.search(before) or CURRENCY_NEAR.match(after)) and not (vals & money):
            bad.append(tok)
    return bad


def keep_supported(text: str, allowed: set[Decimal], money: set[Decimal] | None = None,
                   pct: set[Decimal] | None = None) -> tuple[str, list[str]]:
    """Drop sentences that carry unsupported numbers. Returns (kept text, removed sentences)."""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", (text or "").strip())
    kept, removed = [], []
    for s in sentences:
        (removed if bad_numbers(s, allowed, money, pct) else kept).append(s)
    return " ".join(k for k in kept if k), removed
