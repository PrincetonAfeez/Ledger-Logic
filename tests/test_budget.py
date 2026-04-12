"""Tests for budget allocation and comparison."""

from __future__ import annotations

from typing import cast

import pytest
from ledgerlogic import budget
from ledgerlogic.schemas import BudgetAllocation, BudgetCategoryProfile


def test_allocate_fifty_thirty_twenty_splits_income() -> None:
    cats = budget.starter_categories()
    result = budget.allocate_fifty_thirty_twenty(5000.0, cats)
    assert result["strategy"] == "50/30/20"
    assert result["allocated_total"] + result["remaining"] == pytest.approx(5000.0)
    assert result["allocations"]["Rent"] > 0


def test_allocate_fifty_thirty_twenty_rejects_negative_income() -> None:
    with pytest.raises(ValueError, match="Income cannot be negative"):
        budget.allocate_fifty_thirty_twenty(-1.0, budget.starter_categories())


def test_allocate_priority_weighted_covers_full_income() -> None:
    cats = budget.starter_categories()
    result = budget.allocate_priority_weighted(3000.0, cats)
    assert result["allocated_total"] == pytest.approx(3000.0)
    assert result["remaining"] == pytest.approx(0.0)


def test_compare_actual_to_budget_over_under() -> None:
    cats = budget.starter_categories()
    allocation = budget.allocate_fifty_thirty_twenty(1000.0, cats)
    actuals = {name: 0.0 for name in allocation["allocations"]}
    first = next(iter(actuals))
    actuals[first] = allocation["allocations"][first] + 50.0
    comparison = budget.compare_actual_to_budget(allocation, actuals)
    assert comparison["total_overage"] >= 50.0
    over_rows = [r for r in comparison["rows"] if r["status"] == "OVER"]
    assert len(over_rows) >= 1


def test_compare_strategies_runs_all_three() -> None:
    results = budget.compare_strategies(4000.0, budget.starter_categories())
    assert set(results.keys()) == {"50/30/20", "Priority Weighted", "Zero Based"}


def test_validate_category_rejects_duplicate_name() -> None:
    cats = budget.starter_categories()
    first = next(iter(cats))
    errors = budget.validate_category(first, cats[first], {first})
    assert any("Duplicate" in e for e in errors)


def test_distribute_pool_zero_weight_warns() -> None:
    cats: dict[str, BudgetCategoryProfile] = {
        "A": cast(BudgetCategoryProfile, {"tier": "Needs", "weight": 0, "priority": 5, "actual_spend": 0.0, "budgeted_amount": 0.0}),
        "B": cast(BudgetCategoryProfile, {"tier": "Needs", "weight": 0, "priority": 5, "actual_spend": 0.0, "budgeted_amount": 0.0}),
    }
    alloc, warns = budget.distribute_pool_by_weight(["A", "B"], cats, 100.0)
    assert alloc["A"] == 0.0 and alloc["B"] == 0.0
    assert warns


def test_allocate_zero_based_warns_unknown_manual_categories() -> None:
    cats = budget.starter_categories()
    result = budget.allocate_zero_based(5000.0, cats, {"Rent": 100.0, "NotACategory": 50.0})
    assert any("unknown" in w.lower() for w in result["warnings"])


def test_compare_actual_includes_unbudgeted_spend_row() -> None:
    only = cast(
        BudgetCategoryProfile,
        {"tier": "Needs", "weight": 1, "priority": 5, "actual_spend": 0.0, "budgeted_amount": 0.0},
    )
    allocation = cast(
        BudgetAllocation,
        {
            "strategy": "test",
            "allocations": {"Solo": 1000.0},
            "categories": {"Solo": only},
            "allocated_total": 1000.0,
            "remaining": 0.0,
            "warnings": [],
        },
    )
    comparison = budget.compare_actual_to_budget(allocation, {"Solo": 0.0, "Ghost": 40.0})
    names = {r["category"] for r in comparison["rows"]}
    assert "Ghost" in names
    ghost = next(r for r in comparison["rows"] if r["category"] == "Ghost")
    assert ghost["budgeted"] == 0.0
    assert ghost["actual"] == pytest.approx(40.0)
    assert ghost["tier"] == "Unknown"
    assert ghost["percentage_of_budget"] is None


def test_build_redistribution_suggestion_finds_donor() -> None:
    cats = budget.starter_categories()
    allocation = budget.allocate_fifty_thirty_twenty(2000.0, cats)
    actuals = {n: allocation["allocations"].get(n, 0.0) for n in allocation["allocations"]}
    over = next(iter(actuals))
    actuals[over] = allocation["allocations"][over] + 100.0
    under = next(n for n in actuals if n != over)
    actuals[under] = max(0.0, allocation["allocations"][under] - 300.0)
    comparison = budget.compare_actual_to_budget(allocation, actuals)
    suggestions = budget.build_redistribution_suggestions(comparison)
    assert isinstance(suggestions, list)


def test_aggregate_actual_spending_maps_health_subcategory_to_insurance() -> None:
    records = [
        {
            "date": "2024-01-01",
            "merchant": "CVS",
            "amount": 25.0,
            "category": "Health",
            "subcategory": "Health",
        }
    ]
    totals = budget.aggregate_actual_spending(records)
    assert totals["Insurance"] == pytest.approx(25.0)
    assert "Health" not in totals
