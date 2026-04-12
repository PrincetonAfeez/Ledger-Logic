"""Unified LedgerLogic CLI: argparse subcommands and interactive dashboard."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from . import (
    analyzer,
    budget,
    categorizer,
    change_maker,
    investment,
    reconciler,
    report_builder,
)
from .parsing import parse_date
from .schemas import CategorizedRecord, FinancialReportParams, InvestmentScenario
from .storage import (
    get_budget_profile_path,
    get_categorized_path,
    get_investment_profile_path,
    load_categorized_transactions,
    load_json,
    save_categorized_transactions,
    save_json,
)


def stored_records_for_analysis() -> tuple[list[CategorizedRecord], list[str]]:
    """Load saved categorized transactions and parse dates for analytics."""
    saved, csv_warnings = load_categorized_transactions()
    parsed: list[CategorizedRecord] = []
    skip_warnings: list[str] = list(csv_warnings)
    for index, row in enumerate(saved, start=1):
        merchant_hint = (row.get("merchant") or "").strip() or "(no merchant)"
        try:
            parsed.append(
                cast(
                    CategorizedRecord,
                    {
                        "date": parse_date(str(row["date"])),
                        "merchant": row["merchant"],
                        "amount": float(row["amount"]),
                        "category": row["category"],
                        "subcategory": row.get("subcategory", row["category"]),
                    },
                )
            )
        except (ValueError, TypeError, KeyError) as error:
            skip_warnings.append(f"Skipped stored row {index} ({merchant_hint}): {error}")
    return parsed, skip_warnings


def choose_records(
    file_path: str | None = None, use_mock: bool = False
) -> tuple[list[CategorizedRecord], str]:
    """Pick data from file, saved storage, or mock generator."""
    if use_mock:
        return analyzer.generate_mock_transactions(), "built-in mock data"
    if file_path:
        loaded, warnings, duplicates = analyzer.load_categorized_file(file_path)
        if warnings:
            for warning in warnings:
                print(warning)
        if duplicates:
            print(f"Skipped {len(duplicates)} duplicate rows while loading {file_path}.")
        return loaded, str(file_path)

    saved, load_warnings = stored_records_for_analysis()
    for warning in load_warnings:
        print(warning)
    if saved:
        return saved, str(get_categorized_path())

    return (
        analyzer.generate_mock_transactions(),
        "built-in mock data because no saved import was found",
    )


def import_statement(args: argparse.Namespace) -> int:
    """Run categorization and persist the results."""
    result = categorizer.run_classification(
        file_path=args.file,
        use_mock=args.mock,
        threshold=args.threshold / 100,
    )
    output_path = Path(args.output) if args.output else get_categorized_path()
    saved_path = save_categorized_transactions(result["records"], output_path)

    for warning in result["warnings"]:
        print(warning)
    categorizer.print_summary(result["records"], result["flagged"])
    print()
    print(f"Saved categorized transactions to {saved_path}")
    return 0


def analyze_spending(args: argparse.Namespace) -> int:
    """Run analytics against saved or provided categorized data."""
    records, source_label = choose_records(file_path=args.file, use_mock=args.mock)
    report = analyzer.run_all_reports(records, payday_date=args.payday)
    print(f"Analysis source: {source_label}")
    print()
    analyzer.print_full_analysis(report)
    return 0


def make_change(args: argparse.Namespace) -> int:
    """Run the change-making command."""
    result = change_maker.calculate_change(args.amount, verbose=args.verbose)
    change_maker.print_change_result(result, verbose=args.verbose)
    return 0


def save_scenario_if_requested(scenario: Mapping[str, Any], should_save: bool) -> None:
    """Persist a scenario when the user asks for it."""
    if not should_save:
        return
    path = get_investment_profile_path()
    data = load_json(path, default={})
    data[scenario["name"]] = scenario
    save_json(data, path)
    print(f"Saved scenario to {path}")


def run_investment_projection(args: argparse.Namespace) -> int:
    """Run a quick projection or compare saved scenarios."""
    if args.compare_saved:
        saved = load_json(get_investment_profile_path(), default={})
        print(investment.compare_scenarios(cast(dict[str, InvestmentScenario], saved)))
        return 0

    scenario = investment.default_scenario(args.name)
    scenario["initial_principal"] = args.principal
    scenario["annual_rate"] = args.rate
    scenario["years"] = args.years
    scenario["compounding"] = args.compounding
    scenario["contribution_amount"] = args.monthly if args.contribution_frequency == "monthly" else args.annual_contribution
    scenario["contribution_frequency"] = args.contribution_frequency
    scenario["contribution_timing"] = args.timing
    scenario["inflation_rate"] = args.inflation

    result = investment.project_scenario(scenario)
    print(investment.format_single_projection(result))
    if args.chart:
        print()
        print(investment.build_growth_chart(result))
    save_scenario_if_requested(scenario, args.save)
    return 0


def run_budget(args: argparse.Namespace) -> int:
    """Generate budget allocations and compare them to imported spending."""
    categories = budget.starter_categories()
    records, load_warnings = stored_records_for_analysis()
    for warning in load_warnings:
        print(warning)
    actuals = budget.aggregate_actual_spending(records)

    if args.strategy == "all":
        results = budget.compare_strategies(args.income, categories)
        budget.print_strategy_comparison_table(results)
        if actuals and args.compare_actuals:
            print()
            chosen = results["50/30/20"]
            comparison = budget.compare_actual_to_budget(chosen, actuals)
            budget.print_comparison_report(comparison, args.income)
        if args.save:
            save_json({"income": args.income, "strategy": "all", "actuals": actuals}, get_budget_profile_path())
        return 0

    if args.strategy == "priority":
        allocation = budget.allocate_priority_weighted(args.income, categories)
    elif args.strategy == "zero":
        allocation = budget.allocate_zero_based(args.income, categories)
    else:
        allocation = budget.allocate_fifty_thirty_twenty(args.income, categories)

    budget.print_allocation_table(allocation)
    if actuals and args.compare_actuals:
        print()
        comparison = budget.compare_actual_to_budget(allocation, actuals)
        budget.print_comparison_report(comparison, args.income)

    if args.save:
        save_json(
            {
                "income": args.income,
                "strategy": allocation["strategy"],
                "allocations": allocation["allocations"],
                "actuals": actuals,
            },
            get_budget_profile_path(),
        )
        print(f"Saved budget profile to {get_budget_profile_path()}")
    return 0


def run_reconcile(args: argparse.Namespace) -> int:
    """Compare two sources and optionally export the report."""
    result = reconciler.run_reconciliation(
        source_file=args.source,
        reference_file=args.reference,
        fuzzy_threshold=args.fuzzy / 100,
        date_tolerance=args.date_tolerance,
        amount_tolerance=args.amount_tolerance,
        use_mock=args.mock,
        export_report=args.export,
        output_dir=args.output_dir,
    )
    for warning in result["warnings"]:
        print(warning)
    print(result["report_text"])
    if result["output_path"]:
        print()
        print(f"Report exported to {result['output_path']}")
    return 0


def financial_report_params_from_args(args: argparse.Namespace) -> FinancialReportParams:
    """Map CLI ``report`` / dashboard arguments to :class:`FinancialReportParams`."""
    return {
        "payday": args.payday,
        "income": args.income,
        "monthly": args.monthly,
        "rate": args.rate,
        "years": args.years,
        "inflation": args.inflation,
        "output": args.output,
    }


def build_report(args: argparse.Namespace) -> int:
    """Generate a cross-module finance summary."""
    records, source_label = choose_records(use_mock=args.mock)
    params = financial_report_params_from_args(args)
    report_text, output_path = report_builder.write_full_financial_report(records, source_label, params)
    print(report_text)
    print()
    print(f"Report written to {output_path}")
    return 0


def dashboard_menu() -> int:
    """Run a simple integrated dashboard when no subcommand is provided."""
    valid_choices = {"1", "2", "3", "4", "5", "6", "7", "8"}

    while True:
        print()
        print("LedgerLogic CLI")
        print("1. Import and categorize transactions")
        print("2. Analyze spending patterns")
        print("3. Calculate change")
        print("4. Project investments")
        print("5. Build a budget")
        print("6. Reconcile two files")
        print("7. Generate full report")
        print("8. Quit")
        choice = input("Choose an option: ").strip()
        if choice not in valid_choices:
            print("Please choose one of the listed options.")
            continue

        if choice == "1":
            categorizer.menu()
        elif choice == "2":
            analyzer.menu()
        elif choice == "3":
            change_maker.menu()
        elif choice == "4":
            investment.menu()
        elif choice == "5":
            budget.menu()
        elif choice == "6":
            reconciler.menu()
        elif choice == "7":
            report_args = argparse.Namespace(
                income=5000.0,
                monthly=200.0,
                rate=7.0,
                years=20,
                inflation=2.5,
                payday=15,
                mock=False,
                output=None,
            )
            build_report(report_args)
        elif choice == "8":
            print("Goodbye.")
            return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the LedgerLogic top-level parser."""
    parser = argparse.ArgumentParser(prog="ledgerlogic", description="Unified personal finance command center")
    subparsers = parser.add_subparsers(dest="command")

    import_parser = subparsers.add_parser("import", help="Ingest and categorize a statement")
    import_parser.add_argument("file", nargs="?", help="CSV statement path")
    import_parser.add_argument("--mock", action="store_true", help="Use built-in mock data instead of a file")
    import_parser.add_argument("--threshold", type=float, default=76.0, help="Fuzzy match threshold percent")
    import_parser.add_argument("--output", help="Optional output CSV path")
    import_parser.set_defaults(func=import_statement)

    analyze_parser = subparsers.add_parser("analyze", help="Run pattern analysis")
    analyze_parser.add_argument("file", nargs="?", help="Categorized CSV path")
    analyze_parser.add_argument("--mock", action="store_true", help="Analyze built-in mock data")
    analyze_parser.add_argument("--payday", type=int, default=15, help="Payday date for split analysis")
    analyze_parser.set_defaults(func=analyze_spending)

    change_parser = subparsers.add_parser("change", help="Calculate optimal change")
    change_parser.add_argument("amount", help="Amount like 47.63 or 4763")
    change_parser.add_argument("--verbose", action="store_true", help="Show greedy algorithm trace")
    change_parser.set_defaults(func=make_change)

    invest_parser = subparsers.add_parser("invest", help="Project investment growth")
    invest_parser.add_argument("--name", default="Quick Projection", help="Scenario name")
    invest_parser.add_argument("--principal", type=float, default=10000.0, help="Initial principal")
    invest_parser.add_argument("--monthly", type=float, default=200.0, help="Monthly contribution amount")
    invest_parser.add_argument("--annual-contribution", type=float, default=2400.0, dest="annual_contribution")
    invest_parser.add_argument("--contribution-frequency", choices=["monthly", "annual"], default="monthly")
    invest_parser.add_argument("--rate", type=float, default=7.0, help="Annual interest rate percent")
    invest_parser.add_argument("--years", type=int, default=20, help="Projection length")
    invest_parser.add_argument("--compounding", choices=["monthly", "annual"], default="monthly")
    invest_parser.add_argument("--timing", choices=["start", "end"], default="end", help="Contribution timing")
    invest_parser.add_argument("--inflation", type=float, default=2.5, help="Inflation rate percent")
    invest_parser.add_argument("--chart", action="store_true", help="Show the text growth chart")
    invest_parser.add_argument("--save", action="store_true", help="Save this scenario")
    invest_parser.add_argument("--compare-saved", action="store_true", help="Compare saved scenarios instead")
    invest_parser.set_defaults(func=run_investment_projection)

    budget_parser = subparsers.add_parser("budget", help="Generate a budget")
    budget_parser.add_argument("--income", type=float, required=True, help="Monthly income")
    budget_parser.add_argument("--strategy", choices=["50/30/20", "priority", "zero", "all"], default="50/30/20")
    budget_parser.add_argument("--compare-actuals", action="store_true", help="Compare against saved categorized data")
    budget_parser.add_argument("--save", action="store_true", help="Save the budget profile")
    budget_parser.set_defaults(func=run_budget)

    reconcile_parser = subparsers.add_parser("reconcile", help="Compare two files")
    reconcile_parser.add_argument("source", nargs="?", help="Source CSV path")
    reconcile_parser.add_argument("reference", nargs="?", help="Reference CSV path")
    reconcile_parser.add_argument("--mock", action="store_true", help="Use built-in mock datasets")
    reconcile_parser.add_argument("--fuzzy", type=float, default=80.0, help="Merchant fuzzy threshold percent")
    reconcile_parser.add_argument("--date-tolerance", type=int, default=2, help="Date tolerance in days")
    reconcile_parser.add_argument("--amount-tolerance", type=float, default=0.50, help="Amount tolerance in dollars")
    reconcile_parser.add_argument("--export", action="store_true", help="Export the report to a text file")
    reconcile_parser.add_argument("--output-dir", help="Output directory for exported report")
    reconcile_parser.set_defaults(func=run_reconcile)

    report_parser = subparsers.add_parser("report", help="Generate a full summary report")
    report_parser.add_argument("--income", type=float, default=5000.0, help="Income assumption for budget section")
    report_parser.add_argument("--monthly", type=float, default=200.0, help="Monthly contribution for investment section")
    report_parser.add_argument("--rate", type=float, default=7.0, help="Interest rate for investment section")
    report_parser.add_argument("--years", type=int, default=20, help="Projection length for investment section")
    report_parser.add_argument("--inflation", type=float, default=2.5, help="Inflation assumption")
    report_parser.add_argument("--payday", type=int, default=15, help="Payday date for spend analysis")
    report_parser.add_argument("--mock", action="store_true", help="Use mock transactions if no saved data exists")
    report_parser.add_argument("--output", help="Optional output path for the report text file")
    report_parser.set_defaults(func=build_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Program entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        return dashboard_menu()
    return cast(int, args.func(args))
