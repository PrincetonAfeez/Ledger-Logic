"""Compound interest projector.

**Modeling note:** When compounding is **annual** (one period per year) but
contributions are **monthly**, the simulator does **not** step month-by-month.
Instead, :func:`contribution_for_period` supplies **twelve monthly payments as
one lump** in that yearly period (timing ``start`` / ``end`` applies to that
lump relative to the single interest accrual for the year). That keeps the
loop simple but is **not** identical to twelve separate monthly deposits with
strict year-end compounding—use **monthly compounding** when you want each
contribution aligned with its own accrual interval.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Any, cast

from .schemas import InvestmentScenario, ProjectionResult, ProjectionYearRow
from .storage import format_money

VALID_COMPOUNDING = {"monthly", "annual"}
VALID_CONTRIBUTION_FREQUENCIES = {"monthly", "annual"}
VALID_CONTRIBUTION_TIMING = {"start", "end"}


def validate_scenario(scenario: Mapping[str, Any]) -> list[str]:
    """Validate a scenario in a very explicit student-y way."""
    errors = []

    if not scenario.get("name"):
        errors.append("Scenario name cannot be blank.")

    try:
        if float(scenario.get("initial_principal", 0)) < 0:
            errors.append("Initial principal cannot be negative.")
    except (TypeError, ValueError):
        errors.append("Initial principal has to be numeric.")

    try:
        rate = float(scenario.get("annual_rate", 0))
        if rate < 0:
            errors.append("Interest rate cannot be negative.")
    except (TypeError, ValueError):
        errors.append("Interest rate has to be numeric.")

    try:
        if int(scenario.get("years", 0)) <= 0:
            errors.append("Years must be greater than zero.")
    except (TypeError, ValueError):
        errors.append("Years must be a whole number.")

    try:
        if float(scenario.get("contribution_amount", 0)) < 0:
            errors.append("Contribution amount cannot be negative.")
    except (TypeError, ValueError):
        errors.append("Contribution amount has to be numeric.")

    try:
        if float(scenario.get("inflation_rate", 0)) < 0:
            errors.append("Inflation rate cannot be negative.")
    except (TypeError, ValueError):
        errors.append("Inflation rate has to be numeric.")

    if scenario.get("compounding") not in VALID_COMPOUNDING:
        errors.append("Compounding must be monthly or annual.")

    if scenario.get("contribution_frequency") not in VALID_CONTRIBUTION_FREQUENCIES:
        errors.append("Contribution frequency must be monthly or annual.")

    if scenario.get("contribution_timing") not in VALID_CONTRIBUTION_TIMING:
        errors.append("Contribution timing must be start or end.")

    return errors


def default_scenario(name: str = "Starter") -> InvestmentScenario:
    return cast(
        InvestmentScenario,
        {
            "name": name,
            "initial_principal": 10000.0,
            "annual_rate": 7.0,
            "years": 20,
            "compounding": "monthly",
            "contribution_amount": 200.0,
            "contribution_frequency": "monthly",
            "contribution_timing": "end",
            "inflation_rate": 2.5,
        },
    )


def contribution_for_period(
    scenario: Mapping[str, Any], period_index: int, periods_per_year: int
) -> float:
    """Cash flow for one compounding period.

    With **monthly compounding** (12 periods/year), a monthly contribution is
    one payment per period. With **annual compounding** (1 period/year) and
    monthly frequency, this returns **12 × monthly amount** in that single
    yearly period—see module docstring.
    """
    frequency = scenario["contribution_frequency"]
    amount = float(scenario["contribution_amount"])
    if frequency == "monthly":
        if periods_per_year == 12:
            return amount
        return amount * 12
    if frequency == "annual":
        if periods_per_year == 12:
            return amount if period_index == 1 else 0.0
        return amount
    return 0.0


def project_scenario(scenario: Mapping[str, Any]) -> ProjectionResult:
    """Calculate year-by-year compound growth (see module doc for annual+monthly case)."""
    errors = validate_scenario(scenario)
    if errors:
        raise ValueError(" | ".join(errors))

    years = int(scenario["years"])
    balance = float(scenario["initial_principal"])
    annual_rate = float(scenario["annual_rate"]) / 100
    inflation_rate = float(scenario["inflation_rate"]) / 100
    periods_per_year = 12 if scenario["compounding"] == "monthly" else 1
    contribution_timing = scenario["contribution_timing"]

    rows: list[ProjectionYearRow] = []
    running_contributions = 0.0
    total_interest = 0.0

    for year_number in range(1, years + 1):
        year_start_balance = balance
        year_contributions = 0.0
        year_interest = 0.0

        for period_index in range(1, periods_per_year + 1):
            contribution = contribution_for_period(scenario, period_index, periods_per_year)
            if contribution_timing == "start":
                balance += contribution
                year_contributions += contribution

            period_rate = annual_rate / periods_per_year
            interest = balance * period_rate
            balance += interest
            year_interest += interest

            if contribution_timing == "end":
                balance += contribution
                year_contributions += contribution

        running_contributions += year_contributions
        total_interest += year_interest

        inflation_factor = (1 + inflation_rate) ** year_number if inflation_rate > 0 else 1
        real_balance = balance / inflation_factor
        principal_so_far = float(scenario["initial_principal"]) + running_contributions

        rows.append(
            cast(
                ProjectionYearRow,
                {
                    "year": year_number,
                    "starting_balance": year_start_balance,
                    "contributions": year_contributions,
                    "interest_earned": year_interest,
                    "ending_balance": balance,
                    "real_balance": real_balance,
                    "principal_portion": principal_so_far,
                    "interest_portion": max(0.0, balance - principal_so_far),
                },
            )
        )

    return cast(
        ProjectionResult,
        {
            "scenario": cast(InvestmentScenario, dict(scenario)),
            "rows": rows,
            "ending_balance": balance,
            "total_contributed": float(scenario["initial_principal"]) + running_contributions,
            "total_earned": total_interest,
            "real_ending_balance": rows[-1]["real_balance"] if rows else balance,
            "purchasing_power_loss": balance - (rows[-1]["real_balance"] if rows else balance),
            "warning": "High rate warning: annual rate is above 25%." if float(scenario["annual_rate"]) > 25 else "",
        },
    )


def format_single_projection(result: ProjectionResult) -> str:
    """Create an aligned text table for one scenario."""
    lines = []
    scenario = result["scenario"]
    lines.append(f"Scenario: {scenario['name']}")
    lines.append(
        f"Principal {format_money(float(scenario['initial_principal']))} | "
        f"Rate {float(scenario['annual_rate']):.2f}% | "
        f"Years {scenario['years']} | "
        f"Compounding {scenario['compounding']}"
    )
    if result["warning"]:
        lines.append(result["warning"])
    lines.append("-" * 108)
    lines.append(
        f"{'Year':<6}"
        f"{'Start':>14}"
        f"{'Contrib':>14}"
        f"{'Interest':>14}"
        f"{'End':>16}"
        f"{'Real End':>16}"
        f"{'Note':>10}"
    )
    lines.append("-" * 108)

    for row in result["rows"]:
        milestone_note = "milestone" if row["year"] % 5 == 0 else ""
        lines.append(
            f"{row['year']:<6}"
            f"{format_money(row['starting_balance']):>14}"
            f"{format_money(row['contributions']):>14}"
            f"{format_money(row['interest_earned']):>14}"
            f"{format_money(row['ending_balance']):>16}"
            f"{format_money(row['real_balance']):>16}"
            f"{milestone_note:>10}"
        )

    lines.append("-" * 108)
    lines.append(
        f"Total contributed: {format_money(result['total_contributed'])} | "
        f"Total earned: {format_money(result['total_earned'])}"
    )
    lines.append(
        f"Ending balance: {format_money(result['ending_balance'])} | "
        f"Inflation-adjusted ending balance: {format_money(result['real_ending_balance'])}"
    )
    lines.append(f"Purchasing power loss estimate: {format_money(result['purchasing_power_loss'])}")
    return "\n".join(lines)


def compare_scenarios(scenarios: Mapping[str, InvestmentScenario]) -> str:
    """Compare up to four scenarios side by side."""
    if not scenarios:
        return "No scenarios are saved yet."
    if len(scenarios) > 4:
        return "Please compare four scenarios or fewer."

    results: dict[str, ProjectionResult] = {}
    max_years = 0
    for name, scenario in scenarios.items():
        results[name] = project_scenario(scenario)
        max_years = max(max_years, int(scenario["years"]))

    names = list(results)
    lines = []
    header = f"{'Year':<6}"
    for name in names:
        header += f"{name[:16]:>18}"
    lines.append(header)
    lines.append("-" * len(header))

    for year_number in range(1, max_years + 1):
        line = f"{year_number:<6}"
        for name in names:
            rows = results[name]["rows"]
            if year_number <= len(rows):
                line += f"{format_money(rows[year_number - 1]['ending_balance']):>18}"
            else:
                line += f"{'-':>18}"
        lines.append(line)

    lines.append("-" * len(header))
    contributed_line = f"{'Contrib':<6}"
    earned_line = f"{'Earned':<6}"
    for name in names:
        contributed_line += f"{format_money(results[name]['total_contributed']):>18}"
        earned_line += f"{format_money(results[name]['total_earned']):>18}"
    lines.append(contributed_line)
    lines.append(earned_line)
    return "\n".join(lines)


def build_growth_chart(result: ProjectionResult, width: int = 80) -> str:
    """Draw a text-based bar chart using principal and interest portions."""
    rows = result["rows"]
    if not rows:
        return "No chart data available."

    bar_width = max(20, width - 26)
    max_balance = max(row["ending_balance"] for row in rows) or 1
    encoding = sys.stdout.encoding or "utf-8"
    try:
        "█".encode(encoding)
        principal_char = "█"
        interest_char = "░"
    except (UnicodeEncodeError, LookupError, TypeError):
        principal_char = "#"
        interest_char = "."

    lines = ["Growth chart", f"Legend: {principal_char} principal/contributions, {interest_char} growth"]
    lines.append("-" * min(width, 80))

    for row in rows:
        principal_width = int((row["principal_portion"] / max_balance) * bar_width)
        interest_width = int((row["interest_portion"] / max_balance) * bar_width)
        if principal_width + interest_width == 0:
            principal_width = 1
        bar = (principal_char * principal_width) + (interest_char * interest_width)
        lines.append(f"Year {row['year']:>2} {bar:<{bar_width}} {format_money(row['ending_balance'])}")

    return "\n".join(lines)


def prompt_with_default(prompt: str, default_value: str) -> str:
    entered = input(f"{prompt} [{default_value}]: ").strip()
    return entered if entered else default_value


def _parse_float_field(label: str, raw: str) -> float | None:
    try:
        return float(raw)
    except ValueError:
        print(f"{label} must be a valid number (got {raw!r}).")
        return None


def _parse_years_field(label: str, raw: str) -> int | None:
    try:
        return int(raw, 10)
    except ValueError:
        print(f"{label} must be a whole number (got {raw!r}).")
        return None


def create_or_edit_scenario(existing: InvestmentScenario | None = None) -> InvestmentScenario | None:
    """Collect scenario fields from user input."""
    base = dict(existing) if existing is not None else default_scenario()
    name = prompt_with_default("Scenario name", str(base["name"]))
    principal_raw = prompt_with_default("Initial principal", str(base["initial_principal"]))
    rate_raw = prompt_with_default("Annual interest rate (%)", str(base["annual_rate"]))
    years_raw = prompt_with_default("Years", str(base["years"]))
    compounding = prompt_with_default("Compounding (monthly/annual)", str(base["compounding"]))
    contribution_raw = prompt_with_default("Contribution amount", str(base["contribution_amount"]))
    contribution_frequency = prompt_with_default(
        "Contribution frequency (monthly/annual)", str(base["contribution_frequency"])
    )
    contribution_timing = prompt_with_default("Contribution timing (start/end)", str(base["contribution_timing"]))
    inflation_raw = prompt_with_default("Inflation rate (%)", str(base["inflation_rate"]))

    principal = _parse_float_field("Initial principal", principal_raw)
    rate = _parse_float_field("Annual interest rate (%)", rate_raw)
    years = _parse_years_field("Years", years_raw)
    contribution = _parse_float_field("Contribution amount", contribution_raw)
    inflation = _parse_float_field("Inflation rate (%)", inflation_raw)
    if principal is None or rate is None or years is None or contribution is None or inflation is None:
        return None

    candidate = cast(
        InvestmentScenario,
        {
            "name": name,
            "initial_principal": principal,
            "annual_rate": rate,
            "years": years,
            "compounding": compounding.strip().lower(),
            "contribution_amount": contribution,
            "contribution_frequency": contribution_frequency.strip().lower(),
            "contribution_timing": contribution_timing.strip().lower(),
            "inflation_rate": inflation,
        },
    )

    errors = validate_scenario(candidate)
    if errors:
        print("Scenario had validation issues:")
        for error in errors:
            print(f"- {error}")
        return None
    return candidate


def menu() -> None:
    """Interactive investment menu."""
    scenarios: dict[str, InvestmentScenario] = {}
    valid_choices = {"1", "2", "3", "4", "5", "6", "7"}

    while True:
        print()
        print("LedgerLogic: Compound Interest Projector")
        print("1. Create scenario")
        print("2. View single scenario")
        print("3. Compare scenarios")
        print("4. Edit a scenario")
        print("5. Delete a scenario")
        print("6. Show chart")
        print("7. Quit")
        choice = input("Choose an option: ").strip()
        if choice not in valid_choices:
            print("Please choose a valid menu item.")
            continue

        if choice == "1":
            if len(scenarios) >= 4:
                print("The comparison view is capped at four scenarios, so I'll stop there.")
                continue
            scenario = create_or_edit_scenario()
            if scenario:
                if scenario["name"] in scenarios:
                    confirm = input("That name exists already. Overwrite it? (y/n): ").strip().lower()
                    if confirm != "y":
                        continue
                scenarios[scenario["name"]] = scenario
                print(f"Saved scenario {scenario['name']}.")

        elif choice == "2":
            name = input("Scenario name: ").strip()
            if name not in scenarios:
                print("That scenario name was not found.")
                continue
            result = project_scenario(scenarios[name])
            print(format_single_projection(result))

        elif choice == "3":
            print(compare_scenarios(scenarios))

        elif choice == "4":
            old_name = input("Scenario to edit: ").strip()
            if old_name not in scenarios:
                print("That scenario does not exist.")
                continue
            updated = create_or_edit_scenario(scenarios[old_name])
            if updated is None:
                continue
            new_name = updated["name"]
            if new_name != old_name and new_name in scenarios:
                if input(f"Overwrite existing scenario '{new_name}'? (y/n): ").strip().lower() != "y":
                    continue
            if new_name != old_name:
                scenarios.pop(old_name, None)
            scenarios[new_name] = updated
            print(f"Updated scenario {new_name}.")

        elif choice == "5":
            name = input("Scenario to delete: ").strip()
            if name in scenarios:
                scenarios.pop(name)
                print(f"Deleted {name}.")
            else:
                print("That scenario was not found.")

        elif choice == "6":
            name = input("Scenario name for chart: ").strip()
            if name not in scenarios:
                print("That scenario was not found.")
                continue
            result = project_scenario(scenarios[name])
            print(build_growth_chart(result))

        elif choice == "7":
            print("Exiting investment projector.")
            break


def main() -> None:
    menu()


if __name__ == "__main__":
    main()
