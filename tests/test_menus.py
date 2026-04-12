"""Interactive menus: quick-exit smoke tests and full scripted flows with output checks."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from ledgerlogic import (
    analyzer,
    budget,
    categorizer,
    change_maker,
    investment,
    reconciler,
)
from ledgerlogic import cli as ll_main


def test_dashboard_menu_quit() -> None:
    with patch("builtins.input", return_value="8"):
        code = ll_main.dashboard_menu()
    assert code == 0


def test_dashboard_invalid_then_quit() -> None:
    with patch("builtins.input", side_effect=["99", "8"]):
        code = ll_main.dashboard_menu()
    assert code == 0


def test_categorizer_menu_quit() -> None:
    with patch("builtins.input", return_value="5"):
        categorizer.menu()


def test_analyzer_menu_quit() -> None:
    with patch("builtins.input", return_value="6"):
        analyzer.menu()


def test_change_maker_menu_quit() -> None:
    with patch("builtins.input", return_value="4"):
        change_maker.menu()


def test_budget_menu_quit() -> None:
    with patch("builtins.input", return_value="6"):
        budget.menu()


def test_reconciler_menu_quit() -> None:
    with patch("builtins.input", return_value="5"):
        reconciler.menu()


def test_investment_menu_quit() -> None:
    with patch("builtins.input", return_value="7"):
        investment.menu()


def test_categorizer_menu_classify_mock_then_quit(capsys: pytest.CaptureFixture[str]) -> None:
    """2 = classify mock data, 5 = quit."""
    with patch("builtins.input", side_effect=["2", "5"]):
        categorizer.menu()
    out = capsys.readouterr().out
    assert "Smart Expense Classifier" in out
    assert "Categorized Summary" in out
    assert re.search(r"\$\s*[\d,]+\.\d{2}", out), "expected currency in summary"


def test_analyzer_menu_mock_then_all_reports_then_quit(capsys: pytest.CaptureFixture[str]) -> None:
    """3 = generate mock, 1 = all reports, 6 = quit."""
    with patch("builtins.input", side_effect=["3", "1", "6"]):
        analyzer.menu()
    out = capsys.readouterr().out
    assert "Generated" in out and "mock transactions" in out
    assert "Top merchants by frequency" in out
    assert "Day-of-week breakdown" in out
    assert "Weekend vs weekday average spend" in out


def test_analyzer_menu_individual_report_branch(capsys: pytest.CaptureFixture[str]) -> None:
    """3 = mock, 2 = individual, a = frequency, 6 = quit."""
    with patch("builtins.input", side_effect=["3", "2", "a", "6"]):
        analyzer.menu()
    out = capsys.readouterr().out
    assert "Top merchants by frequency" in out
    assert out.count("Top merchants by frequency") >= 1


def test_change_maker_menu_calculate_then_quit(capsys: pytest.CaptureFixture[str]) -> None:
    """1 = calculate, amount, 4 = quit."""
    with patch("builtins.input", side_effect=["1", "3.87", "4"]):
        change_maker.menu()
    out = capsys.readouterr().out
    assert re.search(r"Change for \$3\.87", out)
    assert re.search(r"Verification: \$3\.87", out)


def test_budget_menu_income_strategy_then_quit(capsys: pytest.CaptureFixture[str]) -> None:
    """1 = set income, 3 = strategy, a = 50/30/20, 6 = quit."""
    with patch("builtins.input", side_effect=["1", "3600", "3", "a", "6"]):
        budget.menu()
    out = capsys.readouterr().out
    assert "Income is now $3,600.00" in out
    assert "50/30/20 allocation" in out
    assert "Allocated total: $3,600.00" in out
    assert "Remaining: $0.00" in out


def test_reconciler_menu_run_mock_then_quit(capsys: pytest.CaptureFixture[str]) -> None:
    """3 = reconcile (no files -> mock), n = skip export, 5 = quit."""
    with patch("builtins.input", side_effect=["3", "n", "5"]):
        reconciler.menu()
    out = capsys.readouterr().out
    assert "No files were loaded, so mock data was used." in out
    assert "LedgerLogic Reconciliation Report" in out
    assert re.search(r"Match rate \(coverage vs larger file\):\s*\d+\.\d%", out)


def test_investment_menu_compare_empty_then_quit(capsys: pytest.CaptureFixture[str]) -> None:
    """3 = compare scenarios (none saved), 7 = quit."""
    with patch("builtins.input", side_effect=["3", "7"]):
        investment.menu()
    out = capsys.readouterr().out
    assert "No scenarios are saved yet." in out


def test_dashboard_opens_change_maker_full_flow_then_quits(capsys: pytest.CaptureFixture[str]) -> None:
    """From dashboard: 3 = change menu, calculate $1.00, quit change, 8 = quit dashboard."""
    with patch("builtins.input", side_effect=["3", "1", "1.00", "4", "8"]):
        code = ll_main.dashboard_menu()
    assert code == 0
    out = capsys.readouterr().out
    assert "LedgerLogic CLI" in out
    assert "Optimal Change Calculator" in out
    assert re.search(r"Change for \$1\.00", out)
