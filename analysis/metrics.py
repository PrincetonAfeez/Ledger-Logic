"""Spending statistics and bundled report generation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast

from ..parsing import parse_date
from ..schemas import (
    AnalysisReport,
    AnomalyReport,
    CategorizedRecord,
    DayOfWeekSpendRow,
    MerchantFrequencySummaryRow,
    MerchantSpendSummaryRow,
    MonthlyTrendLiteral,
    MonthlyTrendRow,
    SpendingAnomalyRow,
    TimeOfMonthSplit,
    WeekendWeekdaySummary,
)
from .records import coerce_analysis_records

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def count_by_merchant(records: Sequence[CategorizedRecord]) -> list[MerchantFrequencySummaryRow]:
    """Top merchants by transaction count without using collections.Counter."""
    counts: dict[str, int] = {}
    for record in records:
        merchant = str(record.get("merchant", "(unknown)"))
        counts[merchant] = counts.get(merchant, 0) + 1
    pairs = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"merchant": m, "count": c} for m, c in pairs[:10]]


def spend_by_merchant(records: Sequence[CategorizedRecord]) -> list[MerchantSpendSummaryRow]:
    """Top merchants by total spend."""
    totals: dict[str, float] = {}
    for record in records:
        merchant = str(record.get("merchant", "(unknown)"))
        totals[merchant] = totals.get(merchant, 0.0) + float(record.get("amount", 0.0))
    pairs = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"merchant": m, "total": float(t)} for m, t in pairs[:10]]


def day_of_week_breakdown(records: Sequence[CategorizedRecord]) -> list[DayOfWeekSpendRow]:
    """Calculate total and average spend per weekday."""
    buckets: dict[str, dict[str, Any]] = {}
    for day_name in DAY_NAMES:
        buckets[day_name] = {"day": day_name, "total": 0.0, "count": 0, "average": 0.0}

    for record in records:
        d_raw = record.get("date")
        if isinstance(d_raw, date):
            d = d_raw
        else:
            d = parse_date(str(d_raw))
        day_name = DAY_NAMES[d.weekday()]
        amt = float(record.get("amount", 0.0))
        buckets[day_name]["total"] += amt
        buckets[day_name]["count"] += 1

    rows: list[DayOfWeekSpendRow] = []
    for day_name in DAY_NAMES:
        row = buckets[day_name]
        if row["count"]:
            row["average"] = float(row["total"]) / int(row["count"])
        rows.append(
            cast(
                DayOfWeekSpendRow,
                {
                    "day": str(row["day"]),
                    "total": float(row["total"]),
                    "count": int(row["count"]),
                    "average": float(row["average"]),
                },
            )
        )
    return rows


def weekend_vs_weekday(records: Sequence[CategorizedRecord]) -> WeekendWeekdaySummary:
    """Compare weekend and weekday spend totals and averages."""
    totals = {"weekend": 0.0, "weekday": 0.0, "weekend_count": 0, "weekday_count": 0}
    for record in records:
        d_raw = record.get("date")
        if isinstance(d_raw, date):
            d = d_raw
        else:
            d = parse_date(str(d_raw))
        amt = float(record.get("amount", 0.0))
        if d.weekday() >= 5:
            totals["weekend"] += amt
            totals["weekend_count"] += 1
        else:
            totals["weekday"] += amt
            totals["weekday_count"] += 1

    weekend_avg = totals["weekend"] / totals["weekend_count"] if totals["weekend_count"] else 0.0
    weekday_avg = totals["weekday"] / totals["weekday_count"] if totals["weekday_count"] else 0.0

    if weekday_avg == 0 and weekend_avg == 0:
        percentage_difference = 0.0
    elif weekday_avg == 0:
        percentage_difference = 100.0
    else:
        percentage_difference = ((weekend_avg - weekday_avg) / weekday_avg) * 100

    return cast(
        WeekendWeekdaySummary,
        {
            "weekend_total": totals["weekend"],
            "weekday_total": totals["weekday"],
            "weekend_avg": weekend_avg,
            "weekday_avg": weekday_avg,
            "percentage_difference": percentage_difference,
        },
    )


def time_of_month_analysis(
    records: Sequence[CategorizedRecord], payday_date: int = 15
) -> TimeOfMonthSplit:
    """Split spending into pre-payday and post-payday windows."""
    results: dict[str, float | int] = {
        "pre_payday_total": 0.0,
        "pre_payday_count": 0,
        "post_payday_total": 0.0,
        "post_payday_count": 0,
    }

    for record in records:
        d_raw = record.get("date")
        if isinstance(d_raw, date):
            d = d_raw
        else:
            d = parse_date(str(d_raw))
        amt = float(record.get("amount", 0.0))
        if d.day < payday_date:
            results["pre_payday_total"] += amt
            results["pre_payday_count"] += 1
        else:
            results["post_payday_total"] += amt
            results["post_payday_count"] += 1

    return cast(TimeOfMonthSplit, results)


def monthly_trends(records: Sequence[CategorizedRecord]) -> list[MonthlyTrendRow]:
    """Calculate total spend per month and whether it rose or fell."""
    totals: dict[str, float] = {}
    for record in records:
        d_raw = record.get("date")
        if isinstance(d_raw, date):
            d = d_raw
        else:
            d = parse_date(str(d_raw))
        key = d.strftime("%Y-%m")
        totals[key] = totals.get(key, 0.0) + float(record.get("amount", 0.0))

    rows: list[MonthlyTrendRow] = [
        cast(MonthlyTrendRow, {"month": month, "total": float(total), "trend": "flat"})
        for month, total in totals.items()
    ]
    rows.sort(key=lambda item: str(item["month"]))

    previous_total: float | None = None
    for row in rows:
        total = float(row["total"])
        trend: MonthlyTrendLiteral
        if previous_total is None:
            trend = "starting point"
        elif total > previous_total:
            trend = "up"
        elif total < previous_total:
            trend = "down"
        else:
            trend = "flat"
        row["trend"] = trend
        previous_total = total
    return rows


def group_category_averages(records: Sequence[CategorizedRecord]) -> dict[str, dict[str, float | int]]:
    """Build category totals and counts before anomaly detection."""
    groups: dict[str, dict[str, float | int]] = {}
    for record in records:
        category = str(record.get("category", "Unknown"))
        if category not in groups:
            groups[category] = {"total": 0.0, "count": 0}
        groups[category]["total"] += float(record.get("amount", 0.0))
        groups[category]["count"] += 1
    for _category, data in groups.items():
        data["average"] = data["total"] / data["count"] if data["count"] else 0.0
    return groups


def detect_anomalies(records: Sequence[CategorizedRecord]) -> AnomalyReport:
    """Flag anything above 3x the category average."""
    category_info = group_category_averages(records)
    anomalies: list[SpendingAnomalyRow] = []
    affected_categories: set[str] = set()

    for record in records:
        category = str(record.get("category", "Unknown"))
        average = float(category_info[category]["average"])
        amt = float(record.get("amount", 0.0))
        if average > 0 and amt > average * 3:
            multiple = amt / average
            d_raw = record.get("date")
            if isinstance(d_raw, date):
                d_val = d_raw
            else:
                d_val = parse_date(str(d_raw))
            anomalies.append(
                cast(
                    SpendingAnomalyRow,
                    {
                        "date": d_val,
                        "merchant": str(record.get("merchant", "")),
                        "amount": amt,
                        "category": category,
                        "category_average": average,
                        "multiple": multiple,
                    },
                )
            )
            affected_categories.add(category)

    anomaly_counts: dict[str, int] = {}
    for category in affected_categories:
        anomaly_counts[category] = 0
    for anomaly in anomalies:
        anomaly_counts[anomaly["category"]] = anomaly_counts.get(anomaly["category"], 0) + 1

    anomalies.sort(key=lambda item: (-item["multiple"], -item["amount"]))
    return cast(
        AnomalyReport,
        {"anomalies": anomalies, "counts": anomaly_counts, "affected_categories": affected_categories},
    )


def run_all_reports(
    records: Sequence[Mapping[str, Any]],
    payday_date: int = 15,
) -> AnalysisReport:
    """Bundle the core analysis into one dictionary."""
    rows = coerce_analysis_records(records)
    return cast(
        AnalysisReport,
        {
            "record_count": len(rows),
            "top_by_frequency": count_by_merchant(rows),
            "top_by_spend": spend_by_merchant(rows),
            "day_of_week": day_of_week_breakdown(rows),
            "weekend_vs_weekday": weekend_vs_weekday(rows),
            "time_of_month": time_of_month_analysis(rows, payday_date=payday_date),
            "monthly_trends": monthly_trends(rows),
            "anomaly_report": detect_anomalies(rows),
        },
    )
