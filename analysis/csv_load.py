"""Load categorized transaction CSV files."""

from __future__ import annotations

import csv
from pathlib import Path

from ..parsing import parse_amount, parse_date
from ..schemas import CategorizedRecord
from .csv_columns import detect_columns
from .records import normalize_analysis_record


def load_categorized_file(
    file_path: str | Path,
) -> tuple[list[CategorizedRecord], list[str], list[CategorizedRecord]]:
    """Read categorized transactions and flag duplicates along the way."""
    records: list[CategorizedRecord] = []
    warnings: list[str] = []
    duplicates: list[CategorizedRecord] = []
    seen: set[tuple[str, str, float]] = set()
    input_path = Path(file_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find file: {input_path}")

    with input_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration:
            return [], ["The file was empty."], []

        mapping = detect_columns(headers)
        for line_number, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue
            try:
                di = mapping["date"]
                mi = mapping["merchant"]
                ai = mapping["amount"]
                ci = mapping["category"]
                si = mapping["subcategory"]
                if di is None or mi is None or ai is None or ci is None:
                    raise ValueError("Row did not contain all expected columns")
                if max(di, mi, ai, ci) >= len(row):
                    raise ValueError("Row did not contain all expected columns")
                parsed_date = parse_date(row[di])
                merchant = row[mi].strip()
                amount = parse_amount(row[ai])
                category = row[ci].strip() or "Unknown"
                if si is not None and si < len(row):
                    subcategory = row[si].strip() or category
                else:
                    subcategory = category
                entry = normalize_analysis_record(
                    {
                        "date": parsed_date,
                        "merchant": merchant,
                        "amount": amount,
                        "category": category,
                        "subcategory": subcategory,
                    }
                )
                duplicate_key = (parsed_date.isoformat(), merchant.lower(), round(amount, 2))
                if duplicate_key in seen:
                    duplicates.append(entry)
                else:
                    seen.add(duplicate_key)
                    records.append(entry)
            except (ValueError, TypeError, KeyError, IndexError) as error:
                warnings.append(f"Skipped line {line_number}: {error}")

    return records, warnings, duplicates
