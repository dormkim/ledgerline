"""LLM writes the words; code checks the numbers. If the LLM is down or wrong, code writes the words."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .numcheck import bad_numbers, evidence, keep_supported

CHARGES = re.compile(r"late fee|interest|penalt|surcharge|collection fee|legal action", re.I)

MAX_ITEMS = 40

EXC_SYSTEM = """You are a careful accounts-receivable/payable assistant explaining bank reconciliation exceptions
to a bookkeeper. For each item write:
- "explanation": at most 2 short sentences on why it was flagged, citing the evidence.
- "next_step": 1 sentence with the concrete action.
Rules: use ONLY numbers that appear in the item (amounts, dates, row numbers, days). Never add, subtract
or estimate anything yourself; if a number is not in the item, do not write it. Plain English, no hedging fluff.
Reply with JSON only: {"items": [{"id": "E1", "explanation": "...", "next_step": "..."}]}"""

FU_SYSTEM = """You draft short, polite payment reminder emails for overdue customer invoices.
Use ONLY the amounts, invoice references, dates and day counts given for that item — do not compute
or invent any number (no late fees, no interest, no totals). 4-6 sentences, friendly and firm, signed "Accounts team".
Reply with JSON only: {"drafts": [{"id": "F1", "subject": "...", "body": "..."}]}"""


def _slim(e: dict) -> dict:
    return {k: e[k] for k in ("id", "kind", "rule", "facts", "hint")} | {
        "bank_lines": e["bank"], "ledger_lines": e["ledger"]}


def template_exc(e: dict) -> tuple[str, str]:
    f, cur = e["facts"], e["facts"].get("currency", "")
    rows = lambda side: ", ".join(f"{side} row {t['row']}" for t in e[side])  # noqa: E731
    if e["kind"] == "amount_mismatch":
        return (f"{rows('bank')} ({f['bank_amount']} {cur}) and {rows('ledger')} ({f['ledger_amount']} {cur}) "
                f"point to the same payment by {f['basis']}, but differ by {f['difference']} {cur}.", e["hint"])
    if e["kind"] == "possible_duplicate":
        return (f"Bank row {e['bank'][0]['row']} repeats bank row {f['duplicate_of_row']} exactly "
                f"({f['amount']} {cur}, same date and text).", e["hint"])
    if e["kind"] == "unreadable_row":
        side = "bank" if e["bank"] else "ledger"
        return f"{side.capitalize()} row {e[side][0]['row']} could not be read: {e['rule']}.", e["hint"]
    side = "bank" if e["kind"] == "unmatched_bank" else "ledger"
    t = e[side][0]
    return (f"{side.capitalize()} row {t['row']} ({t['date']}, {t['amount']} {cur}, {t['name'] or t['desc']}) "
            f"has no counterpart with the same amount.", e["hint"])


def template_fu(f: dict) -> tuple[str, str]:
    ref = f" {f['ref']}" if f["ref"] else ""
    subject = f"Payment reminder: invoice{ref} ({f['amount']} {f['currency']})"
    body = (f"Hello {f['counterparty']},\n\nOur records show invoice{ref} for {f['amount']} {f['currency']} was due on "
            f"{f['due']} and is now {f['days_overdue']} days overdue. We could not find the payment in our bank "
            f"statement up to {f['as_of']}. If you have already paid, please send us the remittance details; "
            f"otherwise we would appreciate payment at your earliest convenience.\n\nThank you,\nAccounts team")
    return subject, body


def narrate(excs: list[dict], fus: list[dict], enabled: bool = True) -> dict:
    """Run both LLM calls in parallel; attach text with its source. Returns timing/meta for the trace."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(_call, EXC_SYSTEM, [_slim(e) for e in excs[:MAX_ITEMS]]) if excs and enabled else None
        b = pool.submit(_call, FU_SYSTEM, fus) if fus and enabled else None
        exc_reply, exc_meta = a.result() if a else (None, {"ms": 0, "error": "nothing to explain" if not excs else "LLM off for this run"})
        fu_reply, fu_meta = b.result() if b else (None, {"ms": 0, "error": "nothing to draft" if not fus else "LLM off for this run"})
    stats = {"llm_sentences_removed": 0, "llm_drafts_rejected": 0}
    by_id = {i.get("id"): i for i in (exc_reply or {}).get("items", []) if isinstance(i, dict)}
    for e in excs:
        _attach_exc(e, by_id.get(e["id"]), exc_meta, stats)
    drafts = {d.get("id"): d for d in (fu_reply or {}).get("drafts", []) if isinstance(d, dict)}
    for f in fus:
        _attach_fu(f, drafts.get(f["id"]), fu_meta, stats)
    return {"exceptions_call": exc_meta, "followups_call": fu_meta, **stats}


def _call(system: str, items: list[dict]):
    return llm.chat_json(system, json.dumps({"items": items}, ensure_ascii=False), max_tokens=3000)


def _attach_exc(e: dict, item: dict | None, meta: dict, stats: dict) -> None:
    tpl_text, tpl_next = template_exc(e)
    if not item:
        why = meta.get("error") or "LLM reply did not cover this item"
        e["narrative"] = {"text": tpl_text, "next_step": tpl_next, "source": "template", "note": why}
        return
    ev = evidence(_slim(e))
    text, gone1 = keep_supported(str(item.get("explanation", "")), *ev)
    nxt, gone2 = keep_supported(str(item.get("next_step", "")), *ev)
    removed = gone1 + gone2
    stats["llm_sentences_removed"] += len(removed)
    e["narrative"] = {"text": text or tpl_text, "next_step": nxt or tpl_next,
                      "source": "llm" if not removed else "llm-checked", "removed": removed,
                      "note": f"{len(removed)} sentence(s) removed: number not in evidence" if removed else None}


def _attach_fu(f: dict, d: dict | None, meta: dict, stats: dict) -> None:
    subject, body = template_fu(f)
    if not d:
        f["draft"] = {"subject": subject, "body": body, "source": "template", "note": meta.get("error") or "LLM skipped"}
        return
    text = str(d.get("subject", "")) + " \n" + str(d.get("body", ""))
    bad = bad_numbers(text, *evidence(f))
    charge = CHARGES.search(text)
    if bad or charge:
        stats["llm_drafts_rejected"] += 1
        why = (f"it wrote {', '.join(bad[:3])}, which is not in the records" if bad
               else f"it mentioned '{charge.group(0)}', which nobody agreed to")
        f["draft"] = {"subject": subject, "body": body, "source": "template", "note": f"LLM draft rejected: {why}"}
        return
    f["draft"] = {"subject": d.get("subject") or subject, "body": d.get("body") or body, "source": "llm", "note": None}
