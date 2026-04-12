"""Tests for spending analysis and categorized CSV loading."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from ledgerlogic import analyzer


def test_run_all_reports_structure() -> None:
    records = analyzer.generate_mock_transactions()[:20]
    report = analyzer.run_all_reports(records, payday_date=15)
    assert report["record_count"] == len(records)
    assert "top_by_frequency" in report
    assert "anomaly_report" in report
    assert isinstance(report["weekend_vs_weekday"]["percentage_difference"], float)


def test_print_full_analysis_outputs_sections(capsys) -> None:
    records = analyzer.generate_mock_transactions()[:5]
    report = analyzer.run_all_reports(records)
    analyzer.print_full_analysis(report, duplicate_count=2)
    out = capsys.readouterr().out
    assert "Top merchants by frequency" in out
    assert "Day-of-week breakdown" in out
    assert "Duplicate transactions skipped during load: 2" in out


def test_load_categorized_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "cat.csv"
    path.write_text(
        "date,merchant,amount,category\n"
        "2024-01-15,Test Mart,12.34,Shopping\n",
        encoding="utf-8",
    )
    records, warnings, dups = analyzer.load_categorized_file(path)
    assert not warnings
    assert not dups
    assert len(records) == 1
    assert records[0]["date"] == date(2024, 1, 15)
    assert records[0]["merchant"] == "Test Mart"
    assert records[0]["amount"] == pytest.approx(12.34)
    assert records[0]["subcategory"] == "Shopping"


def test_load_categorized_file_maps_subcategory_column(tmp_path: Path) -> None:
    path = tmp_path / "two_level.csv"
    path.write_text(
        "date,merchant,amount,category,sub category\n"
        "2024-02-01,Store,5.00,Food,Dining\n",
        encoding="utf-8",
    )
    records, warnings, dups = analyzer.load_categorized_file(path)
    assert not warnings
    assert not dups
    assert len(records) == 1
    assert records[0]["category"] == "Food"
    assert records[0]["subcategory"] == "Dining"


def test_run_all_reports_rejects_invalid_record() -> None:
    bad = [{"date": "not-a-date", "merchant": "x", "amount": 1.0, "category": "c"}]
    with pytest.raises(ValueError, match="Invalid record at index 0"):
        analyzer.run_all_reports(bad)


def test_detect_anomalies_flags_large_purchase() -> None:
    records = [
        {"date": date(2024, 1, 1), "merchant": "A", "amount": 10.0, "category": "Food"},
        {"date": date(2024, 1, 2), "merchant": "B", "amount": 10.0, "category": "Food"},
        {"date": date(2024, 1, 3), "merchant": "C", "amount": 10.0, "category": "Food"},
        {"date": date(2024, 1, 4), "merchant": "D", "amount": 100.0, "category": "Food"},
    ]
    rep = analyzer.detect_anomalies(records)
    assert len(rep["anomalies"]) >= 1
