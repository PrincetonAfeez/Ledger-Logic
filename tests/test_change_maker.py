"""Tests for optimal change calculation."""

from __future__ import annotations

import pytest
from ledgerlogic import change_maker


def test_parse_amount_to_cents_dollars() -> None:
    parsed = change_maker.parse_amount_to_cents("$14.73")
    assert parsed["cents"] == 1473
    assert parsed["dollars"] == pytest.approx(14.73)


def test_parse_amount_to_cents_integer_cents_when_no_dollar_sign() -> None:
    parsed = change_maker.parse_amount_to_cents("1473")
    assert parsed["cents"] == 1473


def test_calculate_change_verifies_total() -> None:
    result = change_maker.calculate_change("5.47", verbose=False)
    assert result["ok"] is True
    assert result["verification"] == pytest.approx(5.47)
    assert result["bill_count"] + result["coin_count"] > 0


def test_calculate_change_zero_message() -> None:
    result = change_maker.calculate_change("0")
    assert result["message"]
    assert result["breakdown"] == {}


def test_parse_negative_rejected() -> None:
    with pytest.raises(ValueError, match="Negative"):
        change_maker.parse_amount_to_cents("-1.00")


def test_parse_leading_plus_dollars() -> None:
    parsed = change_maker.parse_amount_to_cents("+10.25")
    assert parsed["cents"] == 1025


def test_parse_scientific_notation_rejected() -> None:
    with pytest.raises(ValueError, match="Scientific notation"):
        change_maker.parse_amount_to_cents("1e2")


def test_parse_dollar_prefix_makes_long_integer_dollars_not_cents() -> None:
    parsed = change_maker.parse_amount_to_cents("$1473")
    assert parsed["cents"] == 147_300


def test_print_change_result_smoke(capsys) -> None:
    result = change_maker.calculate_change("10.00", verbose=False)
    change_maker.print_change_result(result, verbose=False)
    out = capsys.readouterr().out
    assert "Change for" in out
    assert "Verification" in out
