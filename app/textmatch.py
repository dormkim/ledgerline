"""Name and reference evidence between a bank line and a ledger line. Pure functions, no LLM."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from functools import lru_cache

LEGAL = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "llc", "llp", "plc", "gmbh",
         "ag", "sa", "sas", "srl", "bv", "nv", "pty", "the", "kg", "ug", "oy", "ab", "as"}
NOISE = {"payment", "pmt", "pymt", "transfer", "trf", "xfer", "ach", "wire", "sepa", "card", "pos", "debit", "credit",
         "direct", "dd", "deposit", "from", "to", "ref", "inv", "invoice", "bill", "online", "purchase", "ueberweisung",
         "lastschrift", "gutschrift", "fee", "and", "of", "for", "via"}
_YEAR = re.compile(r"^(19|20)\d\d$")
REF_RE = re.compile(r"\b(?:[A-Z]{1,5}[-#/ ]?\d{2,}[-\d]*|\d{4,})\b", re.I)


@lru_cache(maxsize=20_000)
def tokens(s: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9]+", (s or "").lower())
    return frozenset(w for w in words if w not in LEGAL and w not in NOISE and not w.isdigit() and len(w) > 1)


@lru_cache(maxsize=50_000)
def name_score(ledger_name: str, bank_text: str) -> float:
    """0..1. Ledger names are clean ('Acme Corporation'); bank text is noisy ('ACME CORP *INV-1042')."""
    a, b = tokens(ledger_name), tokens(bank_text)
    if not a or not b:
        return 0.0
    overlap = len(a & b) / len(a)
    prefix = max((1.0 for x in a for y in b if len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x))),
                 default=0.0) * 0.8
    fuzzy = SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio() * 0.8
    return round(max(overlap, prefix, fuzzy), 2)


@lru_cache(maxsize=20_000)
def refs(s: str) -> frozenset[str]:
    """Reference keys: 'INV-1042' → {'inv1042', '1042'}; long digit runs kept as-is."""
    out = set()
    for m in REF_RE.findall(s or ""):
        key = re.sub(r"[^a-z0-9]", "", m.lower())
        if _YEAR.match(key):
            continue
        out.add(key)
        digits = re.sub(r"\D", "", key).lstrip("0")
        # Digits alone count only with 3+ significant digits: 'SUITE 12' must not meet 'INV-0012'.
        # A bare year ('FA-2026/0431') is never evidence either.
        if len(digits) >= 3 and not _YEAR.match(digits):
            out.add(digits)
    return frozenset(out)


def ref_hit(ledger_ref: str, ledger_text: str, bank_text: str) -> str | None:
    """Return the shared reference if the bank text carries the ledger's reference."""
    mine = set(refs(ledger_ref)) | (set(refs(ledger_text)) if not ledger_ref else set())
    if ledger_ref and not mine:  # short refs like 'A7' still count, but only as a whole token
        mine = {re.sub(r"[^a-z0-9]", "", ledger_ref.lower())}
    theirs = set(refs(bank_text)) | {w for w in re.findall(r"[a-z0-9]+", bank_text.lower())}
    shared = {m for m in mine if m and m in theirs}
    return max(shared, key=len) if shared else None
