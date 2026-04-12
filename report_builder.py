"""Assemble the cross-module text report used by ``ledgerlogic report`` and the dashboard."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

from .schemas import (
    AnalysisReport,
    BudgetComparisonResult,
    CategorizedRecord,
    CategorySummaryRow,
    ChangeResult,
    FinancialReportParams,
    InvestmentScenario,
    MerchantSpendSummaryRow,
    ProjectionResult,
)
from .storage import format_money, get_report_path, write_text_report


def _records_for_category_summary(records: list[CategorizedRecord]) -> list[CategorizedRecord]:
    """Shape rows for :func:`ledgerlogic.categorizer.summarize_categories`.

    ``summarize_categories`` expects string dates and optional confidence metadata; for
    report aggregation we supply neutral placeholders (``confidence`` 1.0,
    ``match_type`` ``"loaded"``) so category totals match the same amounts as the main
    record list.
    """
    shaped: list[CategorizedRecord] = []
    for record in records:
        date_val = record["date"]
        if isinstance(date_val, date):
            date_out = date_val.isoformat()
        else:
            date_out = str(date_val)
        shaped.append(
            cast(
                CategorizedRecord,
                {
                    "date": date_out,
                    "merchant": record["merchant"],
                    "amount": float(record["amount"]),
                    "category": record["category"],
                    "subcategory": record.get("subcategory", record["category"]),
                    "confidence": 1.0,
                    "match_type": "loaded",
                },
            )
        )
    return shaped


def _report_header_lines(source_label: str, record_count: int) -> list[str]:
    lines = [
        "LedgerLogic Financial Summary",
        "=" * 32,
        f"Data source: {source_label}",
        f"Transactions analyzed: {record_count}",
        "",
    ]
    return lines


def _spending_section_lines(
    spend_report: AnalysisReport,
    top_category: CategorySummaryRow,
    top_merchant: MerchantSpendSummaryRow,
) -> list[str]:
    lines = [
        "Spending snapshot",
        "-" * 32,
        f"Top category: {top_category['category']} at {format_money(top_category['total'])}",
        f"Top merchant by spend: {top_merchant['merchant']} at {format_money(top_merchant['total'])}",
        (
            "Weekend vs weekday average difference: "
            f"{spend_report['weekend_vs_weekday']['percentage_difference']:.1f}%"
        ),
        f"Anomalies flagged: {len(spend_report['anomaly_report']['anomalies'])}",
        "",
    ]
    return lines


def _budget_section_lines(params: FinancialReportParams, comparison: BudgetComparisonResult) -> list[str]:
    lines = [
        "Budget snapshot",
        "-" * 32,
        f"Income assumption: {format_money(params['income'])}",
        f"Budgeted total: {format_money(comparison['total_budgeted'])}",
        f"Actual categorized spend: {format_money(comparison['total_actual'])}",
        f"Total overage: {format_money(comparison['total_overage'])}",
        f"Total surplus: {format_money(comparison['total_surplus'])}",
    ]
    top_overages = [row for row in comparison["rows"] if row["status"] == "OVER"][:3]
    if top_overages:
        for row in top_overages:
            pct = row["percentage_of_budget"]
            pct_part = f"{pct:.0f}%" if pct is not None else "n/a (unbudgeted)"
            lines.append(
                f"Over budget: {row['category']} at {pct_part} "
                f"({format_money(row['difference'])} over)"
            )
    else:
        lines.append("No categories were over budget in this snapshot.")
    lines.append("")
    return lines


def _investment_section_lines(params: FinancialReportParams, result: ProjectionResult) -> list[str]:
    lines = [
        "Investment snapshot",
        "-" * 32,
        (
            f"{params['years']}-year projection at {params['rate']:.2f}% "
            f"with {format_money(params['monthly'])} monthly contributions"
        ),
        f"Projected ending balance: {format_money(result['ending_balance'])}",
        f"Inflation-adjusted ending balance: {format_money(result['real_ending_balance'])}",
        f"Purchasing power loss estimate: {format_money(result['purchasing_power_loss'])}",
        "",
    ]
    return lines


def _change_section_lines(
    change_result: ChangeResult, denomination_labels: dict[int, dict[str, str]]
) -> list[str]:
    lines = [
        "Change snapshot",
        "-" * 32,
        (
            "Absolute budget vs actual gap (cash denomination breakdown): "
            f"{format_money(change_result['verification'])}"
        ),
    ]
    for value in sorted(change_result["breakdown"], reverse=True):
        lines.append(f"{denomination_labels[value]['name']}: {change_result['breakdown'][value]}")
    lines.append("")
    return lines


def _top_merchant_row(spend_report: AnalysisReport) -> MerchantSpendSummaryRow:
    rows = spend_report["top_by_spend"]
    if rows:
        return rows[0]
    return {"merchant": "N/A", "total": 0.0}


def build_financial_summary_lines(
    records: list[CategorizedRecord],
    source_label: str,
    params: FinancialReportParams,
) -> list[str]:
    """Build report body lines (no trailing newline join).

    The change-maker section uses the **absolute** difference between total actual
    categorized spend and the 50/30/20 budget total as the dollar amount split into
    bills and coins (magnitude only, not signed over vs under).
    """
    from . import analyzer, budget, categorizer, change_maker, investment

    spend_report: AnalysisReport = analyzer.run_all_reports(records, payday_date=params["payday"])
    category_summary = categorizer.summarize_categories(_records_for_category_summary(records))

    actuals = budget.aggregate_actual_spending(records)
    budget_plan = budget.allocate_fifty_thirty_twenty(params["income"], budget.starter_categories())
    budget_comparison = budget.compare_actual_to_budget(budget_plan, actuals)

    scenario = cast(
        InvestmentScenario,
        {
            **dict(investment.default_scenario("Report Projection")),
            "contribution_amount": params["monthly"],
            "annual_rate": params["rate"],
            "years": params["years"],
            "inflation_rate": params["inflation"],
        },
    )
    investment_result = investment.project_scenario(scenario)

    net_budget_gap = abs(round(budget_comparison["total_actual"] - budget_comparison["total_budgeted"], 2))
    change_result = change_maker.calculate_change(f"{net_budget_gap:.2f}", verbose=False)

    top_category: CategorySummaryRow = (
        category_summary[0]
        if category_summary
        else {"category": "N/A", "total": 0.0, "count": 0}
    )
    top_merchant = _top_merchant_row(spend_report)

    lines: list[str] = []
    lines.extend(_report_header_lines(source_label, len(records)))
    lines.extend(_spending_section_lines(spend_report, top_category, top_merchant))
    lines.extend(_budget_section_lines(params, budget_comparison))
    lines.extend(_investment_section_lines(params, investment_result))
    lines.extend(_change_section_lines(change_result, change_maker.DENOMINATIONS))
    out = params["output"]
    lines.append(f"Saved report path: {Path(out) if out else get_report_path()}")
    return lines


def write_full_financial_report(
    records: list[CategorizedRecord],
    source_label: str,
    params: FinancialReportParams,
) -> tuple[str, Path]:
    """Compose the report, write it to disk, and return ``(text, path_written)``."""
    report_text = "\n".join(build_financial_summary_lines(records, source_label, params))
    output_path = Path(params["output"]) if params["output"] else get_report_path()
    written_path = write_text_report(report_text, output_path)
    return report_text, written_path
