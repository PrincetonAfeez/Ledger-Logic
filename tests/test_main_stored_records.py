"""Tests for loading stored categorized rows into analysis records."""

from __future__ import annotations

from ledgerlogic import cli as ll_main


def test_stored_records_for_analysis_warns_on_bad_rows(monkeypatch) -> None:
    bad_rows = [
        {
            "date": "not-a-date",
            "merchant": "Test Mart",
            "amount": 10.0,
            "category": "Shopping",
            "subcategory": "Shopping",
        }
    ]
    monkeypatch.setattr(ll_main, "load_categorized_transactions", lambda: (bad_rows, []))

    records, warnings_list = ll_main.stored_records_for_analysis()

    assert records == []
    assert len(warnings_list) == 1
    assert "Skipped stored row 1" in warnings_list[0]
    assert "Test Mart" in warnings_list[0]
