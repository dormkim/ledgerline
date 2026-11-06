"""Read an uploaded CSV into rows. Unreadable input raises InputError — never an empty table."""
from __future__ import annotations

import csv
import io

MAX_BYTES = 2_000_000
MAX_ROWS = 1_500  # per file; keeps one request's matching work bounded on a public URL


class InputError(ValueError):
    """Input we refuse to reconcile. The message is shown to the user as-is."""


def decode(data: bytes | str, label: str) -> str:
    if isinstance(data, str):
        text = data
    else:
        if len(data) > MAX_BYTES:
            raise InputError(f"{label}: file is larger than {MAX_BYTES // 1_000_000} MB")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
    text = text.lstrip("﻿")
    if "\x00" in text:
        raise InputError(f"{label}: looks like a binary file, not CSV")
    printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in text[:4000])
    if text and printable / min(len(text), 4000) < 0.9:
        raise InputError(f"{label}: too many unreadable characters to be a CSV export")
    return text


def read_rows(data: bytes | str, label: str) -> tuple[list[str], list[list[str]], str]:
    """Return (headers, rows, delimiter). Skips blank lines and preamble lines above the header."""
    text = decode(data, label)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise InputError(f"{label}: file is empty")
    delim = _delimiter(lines[:20])
    try:
        rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delim))
    except csv.Error as e:  # e.g. an unclosed quote swallowing the rest of the file
        raise InputError(f"{label}: not a well-formed CSV ({e})") from e
    start = _header_index(rows)
    headers = [h.strip() for h in rows[start]]
    body = [r for r in rows[start + 1:] if any(c.strip() for c in r)]
    if len(headers) < 2:
        raise InputError(f"{label}: found only one column — is this really a CSV export?")
    if not body:
        raise InputError(f"{label}: has a header row but no transactions")
    if len(body) > MAX_ROWS:
        raise InputError(f"{label}: more than {MAX_ROWS} rows; split the file")
    width = len(headers)
    body = [(r + [""] * width)[:width] for r in body]
    return headers, body, delim


def _delimiter(sample: list[str]) -> str:
    best, score = ",", -1
    for d in [",", ";", "\t", "|"]:
        counts = [len(next(csv.reader([ln], delimiter=d))) for ln in sample]
        common = max(set(counts), key=counts.count)
        s = counts.count(common) * (common > 1) * common
        if s > score:
            best, score = d, s
    return best


def _header_index(rows: list[list[str]]) -> int:
    """Banks often put account info above the real header. Pick the first row as wide as the data."""
    widths = [len([c for c in r if c.strip()]) for r in rows]
    target = max(set(widths[-10:]), key=widths[-10:].count)
    for i, w in enumerate(widths):
        if w >= target and w >= 2:
            return i
    return 0
