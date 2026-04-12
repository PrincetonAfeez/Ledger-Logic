"""Normalize and validate rows used by spending analysis."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast

from ..parsing import parse_amount, parse_date
from ..schemas import CategorizedRecord


def normalize_analysis_record(raw: Mapping[str, Any]) -> CategorizedRecord:
    """Build a :class:`CategorizedRecord` and reject unusable rows."""
    if "date" not in raw:
        raise ValueError("missing required field 'date'")
    d_raw = raw["date"]
    if isinstance(d_raw, date):
        parsed_date: date = d_raw
    else:
        parsed_date = parse_date(str(d_raw))

    if "amount" not in raw:
        raise ValueError("missing required field 'amount'")
    amt_raw = raw["amount"]
    if type(amt_raw) is bool:
        raise ValueError("invalid amount type")
    try:
        if isinstance(amt_raw, (int, float)):
            amount = float(amt_raw)
        else:
            amount = parse_amount(str(amt_raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid amount {amt_raw!r}") from exc
    if math.isnan(amount) or math.isinf(amount):
        raise ValueError("amount must be a finite number")

    merchant = str(raw.get("merchant", "")).strip()
    category = str(raw.get("category", "Unknown")).strip() or "Unknown"
    sub_raw = raw.get("subcategory", category)
    subcategory = str(sub_raw).strip() or category

    return cast(
        CategorizedRecord,
        {
            "date": parsed_date,
            "merchant": merchant,
            "amount": amount,
            "category": category,
            "subcategory": subcategory,
        },
    )


def coerce_analysis_records(records: Sequence[Mapping[str, Any]]) -> list[CategorizedRecord]:
    """Validate each mapping; raises :class:`ValueError` with index on first bad row."""
    out: list[CategorizedRecord] = []
    for index, row in enumerate(records):
        try:
            out.append(normalize_analysis_record(row))
        except ValueError as exc:
            raise ValueError(f"Invalid record at index {index}: {exc}") from exc
    return out
