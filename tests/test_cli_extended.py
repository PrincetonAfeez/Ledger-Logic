"""CLI subcommands: structured stdout contracts (beyond --help / change)."""

from __future__ import annotations

import re

from tests.helpers import run_ledgerlogic_cli


def test_import_mock_saved_path_line() -> None:
    r = run_ledgerlogic_cli("import", "--mock")
    assert r.returncode == 0
    assert r.stderr == ""
    assert re.search(r"Saved categorized transactions to .+\.csv", r.stdout)


def test_budget_fifty_thirty_twenty_allocates_full_income() -> None:
    r = run_ledgerlogic_cli("budget", "--income", "4000", "--strategy", "50/30/20")
    assert r.returncode == 0
    assert r.stderr == ""
    assert "50/30/20 allocation" in r.stdout
    assert "Allocated total: $4,000.00" in r.stdout
    assert "Remaining: $0.00" in r.stdout


def test_reconcile_mock_report_header_and_metrics() -> None:
    r = run_ledgerlogic_cli("reconcile", "--mock")
    assert r.returncode == 0
    assert r.stderr == ""
    assert r.stdout.startswith("LedgerLogic Reconciliation Report")
    assert re.search(
        r"Source transactions: \d+ \| Reference transactions: \d+ \| Match rate \(coverage vs larger file\): \d+\.\d%",
        r.stdout,
    )
    assert re.search(r"Discrepancies: \d+", r.stdout)


def test_invest_flat_one_year_contract() -> None:
    r = run_ledgerlogic_cli(
        "invest",
        "--name",
        "CLI Contract",
        "--years",
        "1",
        "--principal",
        "2500",
        "--monthly",
        "0",
        "--rate",
        "0",
        "--inflation",
        "0",
    )
    assert r.returncode == 0
    assert r.stderr == ""
    assert r.stdout.startswith("Scenario: CLI Contract")
    assert "Principal $2,500.00 | Rate 0.00% | Years 1 |" in r.stdout
    assert "Ending balance: $2,500.00 |" in r.stdout


def test_report_mock_section_order_and_key_lines() -> None:
    r = run_ledgerlogic_cli("report", "--mock")
    assert r.returncode == 0
    assert r.stderr == ""
    text = r.stdout
    assert text.index("LedgerLogic Financial Summary") < text.index("Spending snapshot")
    assert text.index("Spending snapshot") < text.index("Budget snapshot")
    assert text.index("Budget snapshot") < text.index("Investment snapshot")
    assert text.index("Investment snapshot") < text.index("Change snapshot")
    assert re.search(r"^Transactions analyzed: \d+\s*$", text, re.MULTILINE)
    assert re.search(r"^Data source:.+\s*$", text, re.MULTILINE)
    assert "Report written to" in text
