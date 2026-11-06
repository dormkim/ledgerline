"""Deterministic matching. Each pass is a named rule so every result can say which rule produced it.

R1 reference + exact amount     R2 exact amount + date window (+ name evidence breaks ties)
R3 split: 2–3 lines sum exactly R4 same reference / same payer, different amount → amount_mismatch
Ties are never broken by guessing: the lines are held and a question is raised.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations

from .reader import Txn
from .textmatch import name_score, ref_hit

WINDOW_DAYS = 7          # policy: bank date within 7 days of the ledger date
REF_WINDOW_DAYS = 45     # with a shared invoice number, real customers pay late
SPLIT_WINDOW_DAYS = 45
NAME_OK = 0.5
MAX_SPLIT = 3
MAX_SPLIT_CANDIDATES = 12  # C(12,2)+C(12,3) = 286 sums per line: bounded work on a public URL
NEAR_PCT = Decimal("0.02")         # R4 by name: amounts within 2% (or 50 units) look like fees / short payments
NEAR_ABS = 50


@dataclass
class Link:
    rule: str
    bank: list[Txn]
    ledger: list[Txn]
    evidence: dict = field(default_factory=dict)


@dataclass
class Result:
    matches: list[Link] = field(default_factory=list)
    mismatches: list[Link] = field(default_factory=list)
    ambiguous: list[dict] = field(default_factory=list)
    held: set = field(default_factory=set)
    notes: list = field(default_factory=list)
    edges: tuple = field(default_factory=lambda: (defaultdict(list), defaultdict(list)), repr=False)


def _days(b: Txn, l: Txn) -> int:
    """Days from the ledger line to the bank line. Customers pay on the due date, not the invoice date,
    so when a due date exists the nearer of the two counts (a 30-day invoice paid on time is 0 days off)."""
    days = (b.date - l.date).days
    if l.due and abs((b.date - l.due).days) < abs(days):
        return (b.date - l.due).days
    return days


def _evidence(b: Txn, l: Txn) -> dict:
    ev = {"days_apart": _days(b, l), "name_score": name_score(l.name or l.desc, b.text),
          "shared_ref": ref_hit(l.ref, l.text, b.text)}
    if l.due and ev["days_apart"] != (b.date - l.date).days:
        ev["days_counted_from"] = "due date"
    return ev


def _key(ev: dict) -> tuple:
    """Strength of a same-amount pair. Equal keys = equally plausible = ask, don't pick."""
    return (ev["shared_ref"] is not None, ev["name_score"] >= NAME_OK, -abs(ev["days_apart"]))


def match_all(bank: list[Txn], ledger: list[Txn], forced: list[tuple[list[int], list[int]]] | None = None) -> Result:
    res = Result()
    free_b = {t.row: t for t in bank}
    free_l = {t.row: t for t in ledger}
    for brows, lrows in forced or []:
        _force(res, free_b, free_l, brows, lrows)
    _one_to_one(res, free_b, free_l)
    _augment(res, free_b, free_l)
    _splits(res, free_b, free_l, many_bank=True)
    _splits(res, free_b, free_l, many_bank=False)
    _mismatches(res, free_b, free_l)
    return res


def _force(res: Result, free_b: dict, free_l: dict, brows: list[int], lrows: list[int]) -> None:
    """A user's answer is applied only if the numbers agree; otherwise it becomes a visible note or a mismatch."""
    if not all(r in free_b for r in brows) or not all(r in free_l for r in lrows) or not brows or not lrows:
        res.notes.append(f"answer bank {brows} / ledger {lrows} ignored: rows unknown or already used")
        return
    bs, ls = [free_b[r] for r in brows], [free_l[r] for r in lrows]
    if len({t.currency for t in bs + ls}) != 1:
        res.notes.append(f"answer bank {brows} / ledger {lrows} ignored: different currencies")
        return
    for r in brows:
        free_b.pop(r)
    for r in lrows:
        free_l.pop(r)
    total_b, total_l = sum(t.amount for t in bs), sum(t.amount for t in ls)
    if total_b == total_l:
        ev = _evidence(bs[0], ls[0]) if len(bs) == len(ls) == 1 else {"parts": len(bs) + len(ls), "sum": str(total_b)}
        res.matches.append(Link("user-confirmed", bs, ls, ev))
    else:
        res.mismatches.append(Link("user-paired, different amount", bs, ls,
                                   {"difference": str(total_b - total_l), "basis": "user answer"}))


def _one_to_one(res: Result, free_b: dict, free_l: dict) -> None:
    by_amount: dict[tuple, list[Txn]] = defaultdict(list)
    for l in free_l.values():
        by_amount[(l.currency, l.amount)].append(l)
    edges, of_b, of_l = [], defaultdict(list), defaultdict(list)
    for b in free_b.values():
        for l in by_amount.get((b.currency, b.amount), []):
            ev = _evidence(b, l)
            if abs(ev["days_apart"]) <= (REF_WINDOW_DAYS if ev["shared_ref"] else WINDOW_DAYS):
                e = (_key(ev), b, l, ev)
                edges.append(e)
                of_b[b.row].append(e)
                of_l[l.row].append(e)
    edges.sort(key=lambda e: e[0], reverse=True)
    for key, b, l, ev in edges:
        if b.row not in free_b or l.row not in free_l or ("b", b.row) in res.held or ("l", l.row) in res.held:
            continue
        rivals_l = [x for k, _, x, _ in of_b[b.row] if k == key and x is not l and x.row in free_l]
        rivals_b = [x for k, x, _, _ in of_l[l.row] if k == key and x is not b and x.row in free_b]
        if (rivals_l or rivals_b) and not _interchangeable([b, *rivals_b]) and not _interchangeable([l, *rivals_l]):
            group_b, group_l = [b, *rivals_b], [l, *rivals_l]
            res.ambiguous.append({"bank": [t.row for t in group_b], "ledger": [t.row for t in group_l],
                                  "amount": str(b.amount), "currency": b.currency,
                                  "why": "same amount, same date distance, no reference or name to tell them apart"
                                  if not key[0] and not key[1] else "candidates carry equally strong evidence"})
            res.held |= {("b", t.row) for t in group_b} | {("l", t.row) for t in group_l}
            continue
        rule = "R1 reference + amount" if ev["shared_ref"] else "R2 amount + date"
        res.matches.append(Link(rule, [free_b.pop(b.row)], [free_l.pop(l.row)], ev))
    res.edges = (of_b, of_l)


def _augment(res: Result, free_b: dict, free_l: dict) -> None:
    """Greedy can strand a pair that had a valid partner. Re-pair one R2 match when that frees two lines.

    Example: bank 500 on Jan 5 and Jan 12, ledger 500 on Jan 6 and Dec 30. Greedy takes the 1-day pair and
    strands the others, though (Jan 5, Dec 30) and (Jan 12, Jan 6) are both inside the window.
    """
    of_b, of_l = res.edges
    changed = True
    while changed:
        changed = False
        for b in list(free_b.values()):
            if ("b", b.row) in res.held:
                continue
            for _, _, l, ev in of_b[b.row]:
                link = next((m for m in res.matches if m.rule.startswith("R2") and m.ledger[0] is l), None)
                if not link:
                    continue
                b0 = link.bank[0]
                alt = next(((x, ev0) for _, _, x, ev0 in of_b[b0.row] if x.row in free_l and ("l", x.row) not in res.held), None)
                if alt:
                    res.matches.remove(link)
                    res.matches.append(Link("R2 amount + date", [b0], [free_l.pop(alt[0].row)], alt[1]))
                    res.matches.append(Link("R2 amount + date", [free_b.pop(b.row)], [l], ev))
                    changed = True
                    break
            if changed:
                break


def _interchangeable(group: list[Txn]) -> bool:
    """Identical lines (e.g. two equal WeWork debits): which one pairs with which changes no number."""
    return len(group) > 1 and len({(t.date, t.amount, t.currency, t.text.lower()) for t in group}) == 1


def _splits(res: Result, free_b: dict, free_l: dict, many_bank: bool) -> None:
    singles, pool = (free_l, free_b) if many_bank else (free_b, free_l)
    one_side, pool_side = ("l", "b") if many_bank else ("b", "l")
    for one in sorted(singles.values(), key=lambda t: t.row):
        if one.row not in singles or (one_side, one.row) in res.held:
            continue
        cands = [t for t in pool.values() if t.currency == one.currency and (t.amount > 0) == (one.amount > 0)
                 and abs(t.amount) < abs(one.amount) and (pool_side, t.row) not in res.held
                 and abs((t.date - one.date).days) <= SPLIT_WINDOW_DAYS and _related(one, t, many_bank)]
        cands = sorted(cands, key=lambda t: t.row)[:MAX_SPLIT_CANDIDATES]
        hits = [c for k in range(2, MAX_SPLIT + 1) for c in combinations(cands, k)
                if sum(t.amount for t in c) == one.amount]
        if len(hits) > 1:
            rows = sorted({t.row for c in hits for t in c})
            combos = [[t.row for t in c] for c in hits[:6]]
            res.ambiguous.append({"bank": rows if many_bank else [one.row], "ledger": [one.row] if many_bank else rows,
                                  "amount": str(one.amount), "currency": one.currency, "split_side": pool_side,
                                  "combos": combos, "why": f"{len(hits)} different combinations add up to this amount"})
            res.held |= {(one_side, one.row)} | {(pool_side, r) for r in rows}
            continue
        if hits:
            group = list(hits[0])
            for t in group:
                pool.pop(t.row)
            singles.pop(one.row)
            b, l = (group, [one]) if many_bank else ([one], group)
            res.matches.append(Link("R3 split sum", b, l, {"parts": len(group), "sum": str(one.amount)}))


def _related(one: Txn, other: Txn, many_bank: bool) -> bool:
    b, l = (other, one) if many_bank else (one, other)
    return ref_hit(l.ref, l.text, b.text) is not None or name_score(l.name or l.desc, b.text) >= NAME_OK


def _mismatches(res: Result, free_b: dict, free_l: dict) -> None:
    for l in sorted(free_l.values(), key=lambda t: t.row):
        if ("l", l.row) in res.held:
            continue
        best = None
        for b in free_b.values():
            if b.currency != l.currency or (b.amount > 0) != (l.amount > 0) or ("b", b.row) in res.held:
                continue
            days = _days(b, l)
            diff = b.amount - l.amount
            if abs(days) > REF_WINDOW_DAYS or abs(diff) >= abs(l.amount):  # cheap filters first; and a "short
                continue                                                   # payment" can't exceed the invoice
            shared = ref_hit(l.ref, l.text, b.text)
            near = abs(diff) <= max(abs(l.amount) * NEAR_PCT, NEAR_ABS)
            by_ref = shared is not None
            by_name = (not by_ref and near and abs(days) <= WINDOW_DAYS
                       and name_score(l.name or l.desc, b.text) >= NAME_OK)
            if by_ref or by_name:
                rank = (by_ref, -abs(diff))
                if best is None or rank > best[0]:
                    best = (rank, b, _evidence(b, l) | {"difference": str(diff),
                                                       "basis": "reference" if by_ref else "name + date"})
        if best:
            b = free_b.pop(best[1].row)
            free_l.pop(l.row)
            res.mismatches.append(Link("R4 same payee, different amount", [b], [l], best[2]))
