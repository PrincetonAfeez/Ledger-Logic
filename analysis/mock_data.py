"""Synthetic categorized transactions for demos and tests."""

from __future__ import annotations

from datetime import date
from typing import cast

from ..categorizer import DEFAULT_RULES
from ..schemas import CategorizedRecord, CategoryRule
from ..textutil import clean_text


def month_start_from_offset(offset: int) -> tuple[int, int]:
    """Get a year/month pair for N months back from today."""
    today = date.today()
    month = today.month - offset
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return year, month


def rule_payload_from_merchant(merchant: str) -> CategoryRule:
    """Use the categorizer rules to attach categories in mock data."""
    normalized = clean_text(merchant)
    for key, payload in DEFAULT_RULES.items():
        rule = clean_text(key)
        if rule in normalized or normalized in rule:
            return payload
    return cast(CategoryRule, {"category": "Unknown", "subcategory": "Unknown"})


def generate_mock_transactions() -> list[CategorizedRecord]:
    """Build six months of repeatable categorized mock transactions."""
    records: list[CategorizedRecord] = []
    template = [
        (1, "Landlord Portal", 1450.00),
        (3, "Comcast Cable", 82.00),
        (5, "Whole Foods", 118.24),
        (7, "Netflix", 15.49),
        (8, "Spotify", 9.99),
        (10, "Shell", 54.12),
        (12, "Amazon Marketplace", 64.70),
        (14, "PGE Utilities", 91.34),
        (17, "Starbucks", 7.45),
        (20, "Trader Joes", 96.55),
        (22, "Uber Trip", 19.40),
        (24, "Walgreens", 22.18),
        (26, "Starbucks", 6.95),
    ]

    for offset in range(5, -1, -1):
        year, month = month_start_from_offset(offset)
        for day_number, merchant, amount in template:
            payload = rule_payload_from_merchant(merchant)
            adjusted_amount = amount + ((month % 3) * 1.15)
            entry = cast(
                CategorizedRecord,
                {
                    "date": date(year, month, min(day_number, 28)),
                    "merchant": merchant,
                    "amount": round(adjusted_amount, 2),
                    "category": payload["category"],
                    "subcategory": payload["subcategory"],
                },
            )
            records.append(entry)

        if offset == 2:
            records.append(
                cast(
                    CategorizedRecord,
                    {
                        "date": date(year, month, 12),
                        "merchant": "Amazon Marketplace",
                        "amount": 420.00,
                        "category": "Shopping",
                        "subcategory": "Shopping",
                    },
                )
            )

        if offset == 1:
            duplicate = cast(
                CategorizedRecord,
                {
                    "date": date(year, month, 17),
                    "merchant": "Starbucks",
                    "amount": 7.45,
                    "category": "Food & Drink",
                    "subcategory": "Dining Out",
                },
            )
            records.append(duplicate.copy())
            records.append(duplicate.copy())

    return records
