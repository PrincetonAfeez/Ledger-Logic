"""Tests for cross-module financial report assembly."""

from __future__ import annotations

from ledgerlogic import report_builder
from ledgerlogic.analyzer import generate_mock_transactions
from ledgerlogic.schemas import FinancialReportParams


def _default_params() -> FinancialReportParams:
    return {
        "payday": 15,
        "income": 5000.0,
        "monthly": 200.0,
        "rate": 7.0,
        "years": 20,
        "inflation": 2.5,
        "output": None,
    }


def test_build_financial_summary_lines_section_order_and_change_line() -> None:
    records = generate_mock_transactions()
    text = "\n".join(report_builder.build_financial_summary_lines(records, "test source", _default_params()))
    assert text.index("LedgerLogic Financial Summary") < text.index("Spending snapshot")
    assert text.index("Spending snapshot") < text.index("Budget snapshot")
    assert text.index("Budget snapshot") < text.index("Investment snapshot")
    assert text.index("Investment snapshot") < text.index("Change snapshot")
    assert "Data source: test source" in text
    assert "Absolute budget vs actual gap (cash denomination breakdown):" in text


def test_build_financial_summary_lines_empty_records() -> None:
    text = "\n".join(
        report_builder.build_financial_summary_lines([], "empty", _default_params())
    )
    assert "Transactions analyzed: 0" in text
    assert "LedgerLogic Financial Summary" in text
    assert "Top merchant by spend: N/A" in text
    assert "Absolute budget vs actual gap (cash denomination breakdown):" in text


def test_write_full_financial_report_writes_file(tmp_path) -> None:
    records = generate_mock_transactions()
    out = tmp_path / "full.txt"
    params = _default_params()
    params["output"] = str(out)
    report_text, written = report_builder.write_full_financial_report(records, "file test", params)
    assert written == out
    assert report_text == out.read_text(encoding="utf-8")
    assert "LedgerLogic Financial Summary" in report_text
