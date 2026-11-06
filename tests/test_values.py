from datetime import date
from decimal import Decimal

import pytest

from app.values import date_order, money_style, parse_date, parse_money


@pytest.mark.parametrize("raw,style,want", [
    ("1,234.56", "dot", "1234.56"), ("1.234,56", "comma", "1234.56"), ("(200.00)", "dot", "-200.00"),
    ("120.00-", "dot", "-120.00"), ("$ 1,200.00", "dot", "1200.00"), ("€ 12,50", "comma", "12.50"),
    ("-0.01", "dot", "-0.01"), ("45.10 DR", "dot", "-45.10"),
])
def test_money(raw, style, want):
    assert parse_money(raw, style) == Decimal(want)


@pytest.mark.parametrize("raw", ["", "n/a", "—"])
def test_money_unreadable_is_none_not_zero(raw):
    assert parse_money(raw) is None


def test_money_style():
    assert money_style(["1.234,56", "12,50"]) == "comma"
    assert money_style(["1,234.56", "12.50"]) == "dot"


def test_date_order_decided_by_values_or_left_open():
    assert date_order(["31/01/2026", "02/03/2026"]) == "dmy"
    assert date_order(["01/31/2026", "02/03/2026"]) == "mdy"
    assert date_order(["01/02/2026", "03/04/2026"]) is None
    assert date_order(["01.02.2026"]) == "dmy"


def test_parse_date_formats():
    assert parse_date("03-Oct-2026", "text") == date(2026, 10, 3)
    assert parse_date("Oct 3, 2026", "text") == date(2026, 10, 3)
    assert parse_date("2026-10-03T00:00:00", "ymd") == date(2026, 10, 3)
    assert parse_date("31.02.2026", "dmy") is None
