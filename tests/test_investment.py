"""Tests for investment scenario validation and projection."""

from __future__ import annotations

import pytest
from ledgerlogic import investment
from ledgerlogic.schemas import InvestmentScenario


def test_parse_float_rejects_non_numeric() -> None:
    assert investment._parse_float_field("X", "abc") is None


def test_parse_years_rejects_non_integer() -> None:
    assert investment._parse_years_field("Years", "3.5") is None


def test_validate_scenario_flags_blank_name() -> None:
    scenario = investment.default_scenario("")
    errors = investment.validate_scenario(scenario)
    assert any("name" in e.lower() for e in errors)


def test_project_scenario_one_year_no_contrib_flat_rate() -> None:
    scenario = investment.default_scenario("T")
    scenario["initial_principal"] = 1000.0
    scenario["annual_rate"] = 0.0
    scenario["years"] = 1
    scenario["contribution_amount"] = 0.0
    scenario["inflation_rate"] = 0.0
    result = investment.project_scenario(scenario)
    assert result["ending_balance"] == pytest.approx(1000.0)
    assert len(result["rows"]) == 1


def test_project_scenario_rejects_invalid() -> None:
    bad = investment.default_scenario("X")
    bad["years"] = 0
    with pytest.raises(ValueError, match="Years"):
        investment.project_scenario(bad)


def test_project_scenario_high_rate_warning() -> None:
    scenario = investment.default_scenario("Risky")
    scenario["annual_rate"] = 30.0
    scenario["years"] = 1
    scenario["contribution_amount"] = 0.0
    result = investment.project_scenario(scenario)
    assert "High rate warning" in result["warning"]


def test_annual_compounding_monthly_contributions_lump_per_year() -> None:
    """Monthly frequency with annual compounding = 12× monthly as one yearly lump."""
    scenario = investment.default_scenario("Lump")
    scenario["initial_principal"] = 0.0
    scenario["annual_rate"] = 0.0
    scenario["years"] = 1
    scenario["compounding"] = "annual"
    scenario["contribution_amount"] = 100.0
    scenario["contribution_frequency"] = "monthly"
    scenario["contribution_timing"] = "end"
    scenario["inflation_rate"] = 0.0
    result = investment.project_scenario(scenario)
    assert result["rows"][0]["contributions"] == pytest.approx(1200.0)
    assert result["ending_balance"] == pytest.approx(1200.0)


def test_monthly_compounding_twelve_distinct_contributions() -> None:
    scenario = investment.default_scenario("Monthly")
    scenario["initial_principal"] = 0.0
    scenario["annual_rate"] = 0.0
    scenario["years"] = 1
    scenario["compounding"] = "monthly"
    scenario["contribution_amount"] = 100.0
    scenario["contribution_frequency"] = "monthly"
    scenario["contribution_timing"] = "end"
    scenario["inflation_rate"] = 0.0
    result = investment.project_scenario(scenario)
    assert result["rows"][0]["contributions"] == pytest.approx(1200.0)


def test_inflation_reduces_real_balance() -> None:
    scenario = investment.default_scenario("Inf")
    scenario["initial_principal"] = 1000.0
    scenario["annual_rate"] = 0.0
    scenario["years"] = 1
    scenario["contribution_amount"] = 0.0
    scenario["inflation_rate"] = 10.0
    result = investment.project_scenario(scenario)
    assert result["rows"][0]["ending_balance"] == pytest.approx(1000.0)
    assert result["rows"][0]["real_balance"] < 1000.0


def test_compare_scenarios_two_names() -> None:
    a: InvestmentScenario = investment.default_scenario("A")
    a["years"] = 1
    b: InvestmentScenario = investment.default_scenario("B")
    b["years"] = 1
    b["initial_principal"] = 5000.0
    text = investment.compare_scenarios({"A": a, "B": b})
    assert "Year" in text
    assert "A" in text and "B" in text


def test_build_growth_chart_smoke() -> None:
    scenario = investment.default_scenario("C")
    scenario["years"] = 2
    scenario["contribution_amount"] = 0.0
    result = investment.project_scenario(scenario)
    chart = investment.build_growth_chart(result)
    assert "Growth chart" in chart
