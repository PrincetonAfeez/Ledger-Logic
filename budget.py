"""Priority-based budget distributor."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from .schemas import (
    BudgetAllocation,
    BudgetCategoryProfile,
    BudgetComparisonResult,
    BudgetComparisonRow,
    CategorizedRecord,
)
from .storage import format_money

VALID_TIERS = {"Needs", "Wants", "Savings"}

# Categorizer uses "Health" for some merchants; starter categories use "Insurance".
ACTUAL_SPEND_CATEGORY_ALIASES: dict[str, str] = {"Health": "Insurance"}


def normalize_actual_spending_category(raw_name: str) -> str:
    """Map transaction labels onto :func:`starter_categories` keys."""
    return ACTUAL_SPEND_CATEGORY_ALIASES.get(raw_name, raw_name)


def starter_categories() -> dict[str, BudgetCategoryProfile]:
    """Return a starter category set that the user can customize."""
    return cast(
        dict[str, BudgetCategoryProfile],
        {
            "Rent": {"tier": "Needs", "weight": 5, "priority": 10, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Groceries": {"tier": "Needs", "weight": 4, "priority": 9, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Insurance": {"tier": "Needs", "weight": 3, "priority": 8, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Transportation": {"tier": "Needs", "weight": 3, "priority": 7, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Utilities": {"tier": "Needs", "weight": 3, "priority": 7, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Dining Out": {"tier": "Wants", "weight": 2, "priority": 4, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Entertainment": {"tier": "Wants", "weight": 2, "priority": 4, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Shopping": {"tier": "Wants", "weight": 2, "priority": 3, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Emergency Fund": {"tier": "Savings", "weight": 3, "priority": 9, "actual_spend": 0.0, "budgeted_amount": 0.0},
            "Retirement": {"tier": "Savings", "weight": 4, "priority": 10, "actual_spend": 0.0, "budgeted_amount": 0.0},
        },
    )


def aggregate_actual_spending(records: list[CategorizedRecord]) -> dict[str, float]:
    """Roll transaction rows into budget category keys (aliases applied)."""
    totals: dict[str, float] = {}
    for record in records:
        raw = str(record.get("subcategory") or record.get("category") or "Unknown")
        category_name = normalize_actual_spending_category(raw)
        if category_name not in totals:
            totals[category_name] = 0.0
        totals[category_name] += float(record.get("amount", 0.0))
    return {key: round(value, 2) for key, value in totals.items()}


def validate_category(name: str, info: dict[str, Any], existing_names: set[str]) -> list[str]:
    """Validate one category profile."""
    errors = []
    if not name:
        errors.append("Category name cannot be blank.")
    if info.get("tier") not in VALID_TIERS:
        errors.append("Tier must be Needs, Wants, or Savings.")
    try:
        if float(info.get("weight", 0)) < 0:
            errors.append("Weight cannot be negative.")
    except (TypeError, ValueError):
        errors.append("Weight has to be numeric.")
    try:
        priority = int(info.get("priority", 0))
        if priority < 1 or priority > 10:
            errors.append("Priority should be from 1 to 10.")
    except (TypeError, ValueError):
        errors.append("Priority has to be a whole number.")
    if name in existing_names:
        errors.append("Duplicate category names are not allowed.")
    return errors


def apply_actual_spending(
    categories: dict[str, BudgetCategoryProfile], actual_spending: dict[str, Any] | None
) -> dict[str, BudgetCategoryProfile]:
    """Copy actual spend values into the category profiles."""
    categories = deepcopy(categories)
    actual_spending = actual_spending or {}
    for name, info in categories.items():
        info["actual_spend"] = round(float(actual_spending.get(name, 0.0)), 2)
    return categories


def distribute_pool_by_weight(
    category_names: list[str], categories: dict[str, BudgetCategoryProfile], pool_amount: float
) -> tuple[dict[str, float], list[str]]:
    """Split one pool across a tier based on weight."""
    warnings = []
    allocations: dict[str, float] = {}
    total_weight = 0.0
    for name in category_names:
        total_weight += float(categories[name]["weight"])

    if total_weight == 0:
        warnings.append("Weights summed to zero for one allocation pool, so nothing was assigned there.")
        for name in category_names:
            allocations[name] = 0.0
        return allocations, warnings

    running_total = 0.0
    for index, name in enumerate(category_names, start=1):
        if index == len(category_names):
            amount = round(pool_amount - running_total, 2)
        else:
            share = float(categories[name]["weight"]) / total_weight
            amount = round(pool_amount * share, 2)
            running_total += amount
        allocations[name] = max(0.0, amount)
    return allocations, warnings


def allocate_fifty_thirty_twenty(income: float, categories: dict[str, BudgetCategoryProfile]) -> BudgetAllocation:
    """Apply the 50/30/20 rule and distribute within tiers."""
    if income < 0:
        raise ValueError("Income cannot be negative.")
    categories = deepcopy(categories)
    tier_pools = {"Needs": income * 0.50, "Wants": income * 0.30, "Savings": income * 0.20}
    warnings = []
    allocations: dict[str, float] = {}

    for tier_name, pool in tier_pools.items():
        tier_names = [name for name, info in categories.items() if info["tier"] == tier_name]
        if not tier_names:
            warnings.append(f"The {tier_name} tier had no categories, so its pool stayed unassigned.")
            continue
        tier_allocations, pool_warnings = distribute_pool_by_weight(tier_names, categories, round(pool, 2))
        warnings.extend(pool_warnings)
        allocations.update(tier_allocations)

    allocated_total = sum(allocations.values())
    for name, amount in allocations.items():
        categories[name]["budgeted_amount"] = amount

    return cast(
        BudgetAllocation,
        {
            "strategy": "50/30/20",
            "allocations": allocations,
            "categories": categories,
            "allocated_total": round(allocated_total, 2),
            "remaining": round(income - allocated_total, 2),
            "warnings": warnings,
        },
    )


def allocate_priority_weighted(income: float, categories: dict[str, BudgetCategoryProfile]) -> BudgetAllocation:
    """Distribute the full budget proportionally by priority score."""
    if income < 0:
        raise ValueError("Income cannot be negative.")
    categories = deepcopy(categories)
    allocations: dict[str, float] = {}
    total_priority = 0
    for info in categories.values():
        total_priority += int(info["priority"])

    if total_priority == 0:
        raise ValueError("Priority scores cannot sum to zero.")

    running_total = 0.0
    names = list(categories)
    for index, name in enumerate(names, start=1):
        if index == len(names):
            amount = round(income - running_total, 2)
        else:
            share = int(categories[name]["priority"]) / total_priority
            amount = round(income * share, 2)
            running_total += amount
        allocations[name] = max(0.0, amount)
        categories[name]["budgeted_amount"] = allocations[name]

    return cast(
        BudgetAllocation,
        {
            "strategy": "Priority Weighted",
            "allocations": allocations,
            "categories": categories,
            "allocated_total": round(sum(allocations.values()), 2),
            "remaining": round(income - sum(allocations.values()), 2),
            "warnings": [],
        },
    )


def build_zero_based_suggestion(income: float, categories: dict[str, BudgetCategoryProfile]) -> dict[str, float]:
    """Create a suggested zero-based plan when the user is not entering amounts manually."""
    ordered_names = sorted(categories, key=lambda name: (categories[name]["tier"], -categories[name]["priority"], -categories[name]["weight"]))
    remaining = round(income, 2)
    allocations: dict[str, float] = {}
    assigned: set[str] = set()

    total_priority = sum(int(info["priority"]) for info in categories.values()) or 1
    for index, name in enumerate(ordered_names, start=1):
        if name in assigned:
            continue
        if index == len(ordered_names):
            amount = remaining
        else:
            share = int(categories[name]["priority"]) / total_priority
            amount = round(income * share, 2)
            if amount > remaining:
                amount = remaining
        allocations[name] = max(0.0, amount)
        remaining = round(remaining - allocations[name], 2)
        assigned.add(name)

    return allocations


def allocate_zero_based(
    income: float,
    categories: dict[str, BudgetCategoryProfile],
    manual_amounts: dict[str, Any] | None = None,
) -> BudgetAllocation:
    """Assign every dollar to categories and do not allow overshoot."""
    if income < 0:
        raise ValueError("Income cannot be negative.")
    categories = deepcopy(categories)
    allocations: dict[str, float] = {}
    warnings: list[str] = []

    source_amounts = manual_amounts if manual_amounts is not None else build_zero_based_suggestion(income, categories)
    if manual_amounts is not None:
        unknown_keys = set(manual_amounts) - set(categories)
        if unknown_keys:
            warnings.append(
                f"Ignored amounts for unknown categories: {', '.join(sorted(unknown_keys))}."
            )
    remaining = round(income, 2)

    for name in categories:
        amount = round(float(source_amounts.get(name, 0.0)), 2)
        if amount < 0:
            raise ValueError("Zero-based budgeting does not allow negative assigned amounts.")
        if amount > remaining:
            raise ValueError(f"{name} would overshoot the remaining budget.")
        allocations[name] = amount
        categories[name]["budgeted_amount"] = amount
        remaining = round(remaining - amount, 2)

    if remaining != 0:
        warnings.append(f"Zero-based plan left {format_money(remaining)} unassigned.")

    return cast(
        BudgetAllocation,
        {
            "strategy": "Zero Based",
            "allocations": allocations,
            "categories": categories,
            "allocated_total": round(sum(allocations.values()), 2),
            "remaining": remaining,
            "warnings": warnings,
        },
    )


def compare_strategies(income: float, categories: dict[str, BudgetCategoryProfile]) -> dict[str, BudgetAllocation]:
    """Run all strategy functions so the user can compare them."""
    return {
        "50/30/20": allocate_fifty_thirty_twenty(income, categories),
        "Priority Weighted": allocate_priority_weighted(income, categories),
        "Zero Based": allocate_zero_based(income, categories),
    }


def compare_actual_to_budget(
    allocation: BudgetAllocation, actual_spending: dict[str, Any]
) -> BudgetComparisonResult:
    """Compare actuals to one budget strategy.

    Includes rows for **actual spending** on names that are not in the allocation
    (budgeted 0, tier ``Unknown``) so unbudgeted spend still appears.
    """
    alloc = allocation["allocations"]
    cats = allocation["categories"]
    all_names = sorted(set(alloc) | set(actual_spending.keys()))
    rows: list[BudgetComparisonRow] = []
    total_actual = 0.0
    total_budgeted = 0.0
    overages: set[str] = set()
    under_budget: set[str] = set()

    for name in all_names:
        budgeted_amount = round(float(alloc.get(name, 0.0)), 2)
        actual = round(float(actual_spending.get(name, 0.0)), 2)
        difference = round(actual - budgeted_amount, 2)
        total_actual += actual
        total_budgeted += budgeted_amount

        if budgeted_amount == 0:
            percentage_of_budget: float | None = None
        else:
            percentage_of_budget = (actual / budgeted_amount) * 100

        if actual > budgeted_amount:
            status = "OVER"
            overages.add(name)
        elif actual < budgeted_amount:
            status = "UNDER"
            under_budget.add(name)
        else:
            status = "EVEN"

        profile = cats.get(name)
        tier = profile["tier"] if profile else "Unknown"
        priority = int(profile["priority"]) if profile else 0

        rows.append(
            cast(
                BudgetComparisonRow,
                {
                    "category": name,
                    "budgeted": round(budgeted_amount, 2),
                    "actual": actual,
                    "difference": difference,
                    "percentage_of_budget": percentage_of_budget,
                    "status": status,
                    "tier": tier,
                    "priority": priority,
                },
            )
        )

    rows.sort(key=lambda item: (item["status"] != "OVER", -abs(item["difference"])))
    return cast(
        BudgetComparisonResult,
        {
            "rows": rows,
            "overages": overages,
            "under_budget": under_budget,
            "total_overage": round(sum(max(0.0, row["difference"]) for row in rows), 2),
            "total_surplus": round(sum(max(0.0, -row["difference"]) for row in rows), 2),
            "total_actual": round(total_actual, 2),
            "total_budgeted": round(total_budgeted, 2),
        },
    )


def donor_allowed(overage_row: BudgetComparisonRow, candidate_row: BudgetComparisonRow) -> bool:
    """Keep redistribution suggestions inside conservative category rules."""
    if candidate_row["status"] != "UNDER":
        return False
    if candidate_row["category"] == overage_row["category"]:
        return False
    if candidate_row["tier"] == overage_row["tier"] and candidate_row["priority"] <= overage_row["priority"]:
        return True
    if overage_row["tier"] == "Needs" and candidate_row["tier"] == "Wants":
        return True
    return False


def build_redistribution_suggestions(comparison: BudgetComparisonResult) -> list[dict[str, Any]]:
    """Suggest how under-budget categories could absorb overages."""
    suggestions: list[dict[str, Any]] = []
    rows = comparison["rows"]
    for overage_row in rows:
        if overage_row["status"] != "OVER":
            continue
        needed = overage_row["difference"]
        donors = []
        for candidate_row in rows:
            if not donor_allowed(overage_row, candidate_row):
                continue
            available = abs(min(0.0, candidate_row["difference"]))
            if available <= 0:
                continue
            amount = min(needed, available)
            if amount > 0:
                donors.append({"from": candidate_row["category"], "amount": round(amount, 2)})
                needed = round(needed - amount, 2)
            if needed <= 0:
                break

        if donors:
            suggestions.append({"category": overage_row["category"], "needed": overage_row["difference"], "donors": donors})
    return suggestions


def print_allocation_table(allocation: BudgetAllocation) -> None:
    print(f"{allocation['strategy']} allocation")
    print(f"{'Category':<18}{'Tier':<10}{'Weight':>8}{'Budgeted':>16}")
    print("-" * 52)
    for name, info in allocation["categories"].items():
        print(f"{name:<18}{info['tier']:<10}{info['weight']:>8}{format_money(allocation['allocations'].get(name, 0.0)):>16}")
    print("-" * 52)
    print(f"Allocated total: {format_money(allocation['allocated_total'])}")
    print(f"Remaining: {format_money(allocation['remaining'])}")
    for warning in allocation["warnings"]:
        print(f"Warning: {warning}")


def print_strategy_comparison_table(results: dict[str, BudgetAllocation]) -> None:
    if not results:
        print("No strategies to compare.")
        return
    categories = list(next(iter(results.values()))["categories"])
    header = f"{'Category':<18}"
    for strategy_name in results:
        header += f"{strategy_name[:16]:>18}"
    print(header)
    print("-" * len(header))
    for category in categories:
        line = f"{category:<18}"
        for _strategy_name, result in results.items():
            line += f"{format_money(result['allocations'].get(category, 0.0)):>18}"
        print(line)


def print_comparison_report(comparison: BudgetComparisonResult, income: float) -> None:
    print(f"{'Category':<18}{'Budgeted':>14}{'Actual':>14}{'Difference':>14}{'Status':>10}")
    print("-" * 70)
    for row in comparison["rows"]:
        marker = "**" if row["status"] == "OVER" else ""
        pct = row["percentage_of_budget"]
        detail = f"{pct:.0f}%" if pct is not None else "n/a"
        print(
            f"{row['category']:<18}"
            f"{format_money(row['budgeted']):>14}"
            f"{format_money(row['actual']):>14}"
            f"{format_money(row['difference']):>14}"
            f"{(marker + row['status'] + ' ' + detail):>10}"
        )

    print("-" * 70)
    print(f"Total income: {format_money(income)}")
    print(f"Total budgeted: {format_money(comparison['total_budgeted'])}")
    print(f"Total spent: {format_money(comparison['total_actual'])}")
    print(f"Total overage: {format_money(comparison['total_overage'])}")
    print(f"Total surplus: {format_money(comparison['total_surplus'])}")

    suggestions = build_redistribution_suggestions(comparison)
    if suggestions:
        print()
        print("Redistribution suggestions")
        for suggestion in suggestions:
            donor_text = ", ".join(f"{item['from']} {format_money(item['amount'])}" for item in suggestion["donors"])
            print(f"{suggestion['category']} could absorb {format_money(suggestion['needed'])} from {donor_text}")


def prompt_float(prompt: str, allow_zero: bool = True) -> float | None:
    entered = input(prompt).strip()
    try:
        value = float(entered)
    except ValueError:
        print("Please enter a numeric value.")
        return None
    if value < 0:
        print("Negative values are not allowed here.")
        return None
    if value == 0 and not allow_zero:
        print("Zero is not allowed for this field.")
        return None
    return value


def add_category(categories: dict[str, BudgetCategoryProfile]) -> None:
    existing: set[str] = set(categories)
    name = input("Category name: ").strip()
    tier = input("Tier (Needs/Wants/Savings): ").strip().title()
    weight = input("Weight: ").strip()
    priority = input("Priority 1-10: ").strip()
    try:
        info = {"tier": tier, "weight": float(weight), "priority": int(priority), "actual_spend": 0.0, "budgeted_amount": 0.0}
    except ValueError:
        print("Weight and priority have to be numeric.")
        return
    errors = validate_category(name, info, existing)
    if errors:
        for error in errors:
            print(error)
        return
    categories[name] = cast(BudgetCategoryProfile, info)
    print(f"Added {name}.")


def edit_category(categories: dict[str, BudgetCategoryProfile]) -> None:
    name = input("Category to edit: ").strip()
    if name not in categories:
        print("That category was not found.")
        return
    info = categories[name]
    new_tier = input(f"Tier [{info['tier']}]: ").strip().title() or info["tier"]
    new_weight_text = input(f"Weight [{info['weight']}]: ").strip()
    new_priority_text = input(f"Priority [{info['priority']}]: ").strip()
    try:
        updated = {
            "tier": new_tier,
            "weight": float(new_weight_text) if new_weight_text else float(info["weight"]),
            "priority": int(new_priority_text) if new_priority_text else int(info["priority"]),
            "actual_spend": float(info["actual_spend"]),
            "budgeted_amount": float(info["budgeted_amount"]),
        }
    except ValueError:
        print("Weight and priority have to stay numeric.")
        return
    errors = validate_category(name, updated, set(categories) - {name})
    if errors:
        for error in errors:
            print(error)
        return
    categories[name] = cast(BudgetCategoryProfile, updated)
    print(f"Updated {name}.")


def remove_category(categories: dict[str, BudgetCategoryProfile]) -> None:
    name = input("Category to remove: ").strip()
    if name in categories:
        categories.pop(name)
        print(f"Removed {name}.")
    else:
        print("That category was not found.")


def enter_actual_spending(categories: dict[str, BudgetCategoryProfile]) -> dict[str, float]:
    actuals: dict[str, float] = {}
    for name in categories:
        entered = input(f"Actual spending for {name} [0]: ").strip()
        if not entered:
            actuals[name] = 0.0
            continue
        try:
            amount = float(entered)
            if amount < 0:
                print("Negative actual spending is not allowed, so I used 0 instead.")
                amount = 0.0
            actuals[name] = amount
        except ValueError:
            print("That number was invalid, so I used 0 instead.")
            actuals[name] = 0.0
    return actuals


def menu() -> None:
    """Interactive budget menu."""
    income = 0.0
    categories = starter_categories()
    actual_spending: dict[str, float] = {}
    last_allocation: BudgetAllocation | None = None
    valid_choices = {"1", "2", "3", "4", "5", "6"}

    while True:
        print()
        print("LedgerLogic: Priority-Based Budget Distributor")
        print("1. Set income")
        print("2. Manage categories")
        print("3. Run a strategy")
        print("4. Run all strategies and compare")
        print("5. Enter actual spending / view comparison")
        print("6. Quit")
        choice = input("Choose an option: ").strip()
        if choice not in valid_choices:
            print("Please choose a valid menu number.")
            continue

        if choice == "1":
            new_income = prompt_float("Monthly income: ", allow_zero=True)
            if new_income is not None:
                income = new_income
                print(f"Income is now {format_money(income)}.")

        elif choice == "2":
            print("a. Add category")
            print("b. Edit category")
            print("c. Remove category")
            print("d. View categories")
            sub = input("Choice: ").strip().lower()
            if sub == "a":
                add_category(categories)
            elif sub == "b":
                edit_category(categories)
            elif sub == "c":
                remove_category(categories)
            elif sub == "d":
                for name, info in categories.items():
                    print(f"{name:<18}{info['tier']:<10}{info['weight']:>6}{info['priority']:>6}")
            else:
                print("That category option was not recognized.")

        elif choice == "3":
            if not categories:
                print("Please add at least one category first.")
                continue
            if income == 0:
                print("Income is zero, so the plan will be all zeros unless you change it.")
            print("a. 50/30/20")
            print("b. Priority weighted")
            print("c. Zero based")
            sub = input("Strategy: ").strip().lower()
            try:
                if sub == "a":
                    last_allocation = allocate_fifty_thirty_twenty(income, categories)
                elif sub == "b":
                    last_allocation = allocate_priority_weighted(income, categories)
                elif sub == "c":
                    last_allocation = allocate_zero_based(income, categories)
                else:
                    print("That strategy key was not recognized.")
                    continue
                print_allocation_table(last_allocation)
            except ValueError as error:
                print(f"Could not run strategy: {error}")

        elif choice == "4":
            if not categories:
                print("Please add categories first.")
                continue
            try:
                results = compare_strategies(income, categories)
                print_strategy_comparison_table(results)
            except ValueError as error:
                print(f"Could not compare strategies: {error}")

        elif choice == "5":
            if last_allocation is None:
                print("Run a strategy first so there is a budget to compare against.")
                continue
            actual_spending = enter_actual_spending(categories)
            comparison = compare_actual_to_budget(last_allocation, actual_spending)
            print_comparison_report(comparison, income)

        elif choice == "6":
            print("Exiting budget allocator.")
            break


def main() -> None:
    menu()


if __name__ == "__main__":
    main()
