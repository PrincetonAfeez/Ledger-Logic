"""Console output for analysis reports."""

from __future__ import annotations

from ..schemas import (
    AnalysisReport,
    AnomalyReport,
    DayOfWeekSpendRow,
    MerchantFrequencySummaryRow,
    MerchantSpendSummaryRow,
    MonthlyTrendRow,
)
from ..storage import format_money


def print_top_frequency(rows: list[MerchantFrequencySummaryRow]) -> None:
    print("Top merchants by frequency")
    print(f"{'Rank':<6}{'Merchant':<28}{'Count':>8}")
    print("-" * 42)
    for index, row in enumerate(rows, start=1):
        print(f"{index:<6}{row['merchant'][:27]:<28}{row['count']:>8}")


def print_top_spend(rows: list[MerchantSpendSummaryRow]) -> None:
    print("Top merchants by spend")
    print(f"{'Rank':<6}{'Merchant':<28}{'Total':>14}")
    print("-" * 48)
    for index, row in enumerate(rows, start=1):
        print(f"{index:<6}{row['merchant'][:27]:<28}{format_money(row['total']):>14}")


def print_day_breakdown(rows: list[DayOfWeekSpendRow]) -> None:
    print("Day-of-week breakdown")
    print(f"{'Day':<12}{'Count':>8}{'Total':>16}{'Average':>16}")
    print("-" * 52)
    for row in rows:
        print(f"{row['day']:<12}{row['count']:>8}{format_money(row['total']):>16}{format_money(row['average']):>16}")


def print_monthly_trends(rows: list[MonthlyTrendRow]) -> None:
    print("Monthly trend tracking")
    print(f"{'Month':<10}{'Total Spend':>16}{'Trend':>12}")
    print("-" * 40)
    for row in rows:
        print(f"{row['month']:<10}{format_money(row['total']):>16}{row['trend']:>12}")


def print_anomalies(report: AnomalyReport) -> None:
    anomalies = report["anomalies"]
    if not anomalies:
        print("No anomalies crossed the 3x category average threshold.")
        return

    print("Anomalies")
    print(f"{'Date':<12}{'Merchant':<26}{'Amount':>12}{'Avg':>12}{'X Over':>10}")
    print("-" * 72)
    for row in anomalies:
        print(
            f"{row['date'].isoformat():<12}"
            f"{row['merchant'][:25]:<26}"
            f"{format_money(row['amount']):>12}"
            f"{format_money(row['category_average']):>12}"
            f"{row['multiple']:>10.2f}"
        )
    print()
    print(f"Affected categories: {', '.join(sorted(report['affected_categories']))}")


def print_full_analysis(report: AnalysisReport, duplicate_count: int = 0) -> None:
    print_top_frequency(report["top_by_frequency"])
    print()
    print_top_spend(report["top_by_spend"])
    print()
    print_day_breakdown(report["day_of_week"])
    print()

    weekend = report["weekend_vs_weekday"]
    print(
        "Weekend vs weekday average spend: "
        f"{format_money(weekend['weekend_avg'])} vs {format_money(weekend['weekday_avg'])} "
        f"({weekend['percentage_difference']:.1f}% difference)"
    )

    time_split = report["time_of_month"]
    print(
        "Time of month split: "
        f"pre-payday {format_money(time_split['pre_payday_total'])} "
        f"vs post-payday {format_money(time_split['post_payday_total'])}"
    )
    print()
    print_monthly_trends(report["monthly_trends"])
    print()
    print_anomalies(report["anomaly_report"])
    print()
    print(f"Duplicate transactions skipped during load: {duplicate_count}")
