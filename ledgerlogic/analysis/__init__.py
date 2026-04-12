"""Spending analysis: CSV loading, validation, metrics, and CLI output."""

from __future__ import annotations

from .csv_columns import detect_columns
from .csv_load import load_categorized_file
from .menu import main, menu
from .metrics import (
    DAY_NAMES,
    count_by_merchant,
    day_of_week_breakdown,
    detect_anomalies,
    group_category_averages,
    monthly_trends,
    run_all_reports,
    spend_by_merchant,
    time_of_month_analysis,
    weekend_vs_weekday,
)
from .mock_data import (
    generate_mock_transactions,
    month_start_from_offset,
    rule_payload_from_merchant,
)
from .output import (
    print_anomalies,
    print_day_breakdown,
    print_full_analysis,
    print_monthly_trends,
    print_top_frequency,
    print_top_spend,
)
from .records import coerce_analysis_records, normalize_analysis_record

__all__ = [
    "DAY_NAMES",
    "coerce_analysis_records",
    "normalize_analysis_record",
    "count_by_merchant",
    "day_of_week_breakdown",
    "detect_anomalies",
    "detect_columns",
    "generate_mock_transactions",
    "group_category_averages",
    "load_categorized_file",
    "main",
    "menu",
    "month_start_from_offset",
    "monthly_trends",
    "print_anomalies",
    "print_day_breakdown",
    "print_full_analysis",
    "print_monthly_trends",
    "print_top_frequency",
    "print_top_spend",
    "rule_payload_from_merchant",
    "run_all_reports",
    "spend_by_merchant",
    "time_of_month_analysis",
    "weekend_vs_weekday",
]
