"""CLI subprocess tests with explicit output contracts."""

from __future__ import annotations

import pytest

from tests.helpers import run_ledgerlogic_cli


def test_cli_help_usage_and_subcommand_set() -> None:
    proc = run_ledgerlogic_cli("--help")
    assert proc.returncode == 0
    assert proc.stderr == ""
    out = proc.stdout
    assert out.startswith("usage: ledgerlogic")
    assert "{import,analyze,change,invest,budget,reconcile,report}" in out
    assert "Ingest and categorize a statement" in out
    assert "Run pattern analysis" in out
    assert "Calculate optimal change" in out
    assert "Project investment growth" in out
    assert "Generate a budget" in out
    assert "Compare two files" in out
    assert "Generate a full summary report" in out


def test_cli_analyze_mock_contract() -> None:
    proc = run_ledgerlogic_cli("analyze", "--mock")
    assert proc.returncode == 0
    assert proc.stderr == ""
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("Analysis source:")
    assert "mock" in lines[0].lower()
    assert any(line.startswith("Top merchants by frequency") for line in lines)
    assert any(line.startswith("Anomalies") for line in lines)


def test_cli_change_exact_money_and_verification_lines() -> None:
    proc = run_ledgerlogic_cli("change", "11.11")
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert "Change for $11.11\n" in proc.stdout or "Change for $11.11" in proc.stdout
    assert "Verification: $11.11 adds back" in proc.stdout


@pytest.mark.parametrize("amount", ["0.99", "100.00"])
def test_cli_change_verification_matches_change_line(amount: str) -> None:
    proc = run_ledgerlogic_cli("change", amount)
    assert proc.returncode == 0
    fmt = f"${float(amount):,.2f}"
    assert f"Change for {fmt}" in proc.stdout
    assert f"Verification: {fmt} adds back" in proc.stdout
