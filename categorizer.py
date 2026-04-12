"""Transaction categorizer.

This file is intentionally function-based and a little uneven because the
project brief asked for a realistic student-code feel instead of something
heavily abstracted.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

from .parsing import parse_amount
from .schemas import (
    CategorizedRecord,
    CategoryRule,
    CategorySummaryRow,
    ClassificationResult,
    RuleMatchResult,
)
from .storage import format_money
from .textutil import clean_text, similarity_ratio

GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RED = "\033[91m"
RESET = "\033[0m"


VALID_CATEGORIES = {
    "Food & Drink",
    "Transportation",
    "Entertainment",
    "Shopping",
    "Utilities",
    "Health",
    "Housing",
    "Income",
    "Travel",
    "Other",
    "Unknown",
}


DEFAULT_RULES: dict[str, CategoryRule] = {
    "starbucks": {"category": "Food & Drink", "subcategory": "Dining Out"},
    "whole foods": {"category": "Food & Drink", "subcategory": "Groceries"},
    "trader joe s": {"category": "Food & Drink", "subcategory": "Groceries"},
    "shell": {"category": "Transportation", "subcategory": "Transportation"},
    "chevron": {"category": "Transportation", "subcategory": "Transportation"},
    "uber": {"category": "Transportation", "subcategory": "Transportation"},
    "lyft": {"category": "Transportation", "subcategory": "Transportation"},
    "netflix": {"category": "Entertainment", "subcategory": "Entertainment"},
    "spotify": {"category": "Entertainment", "subcategory": "Entertainment"},
    "steam": {"category": "Entertainment", "subcategory": "Entertainment"},
    "amazon": {"category": "Shopping", "subcategory": "Shopping"},
    "target": {"category": "Shopping", "subcategory": "Shopping"},
    "walmart": {"category": "Shopping", "subcategory": "Shopping"},
    "cvs": {"category": "Health", "subcategory": "Health"},
    "walgreens": {"category": "Health", "subcategory": "Health"},
    "kaiser": {"category": "Health", "subcategory": "Insurance"},
    "comcast": {"category": "Utilities", "subcategory": "Utilities"},
    "pge": {"category": "Utilities", "subcategory": "Utilities"},
    "at&t": {"category": "Utilities", "subcategory": "Utilities"},
    "landlord": {"category": "Housing", "subcategory": "Rent"},
    "apartment": {"category": "Housing", "subcategory": "Rent"},
    "payroll": {"category": "Income", "subcategory": "Paycheck"},
}


def detect_columns(headers: list[str]) -> dict[str, int | None]:
    """Map CSV headers to indices; delegates to :mod:`ledgerlogic.analysis.csv_columns`.

    Import is lazy so this module can load before :mod:`ledgerlogic.analysis` (which
    references categorizer rules for mock data).
    """
    from .analysis.csv_columns import detect_columns as _analysis_detect_columns

    return _analysis_detect_columns(headers)


def read_transaction_file(file_path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read CSV rows and normalize them into transaction dictionaries."""
    transactions: list[dict[str, Any]] = []
    warnings: list[str] = []
    input_path = Path(file_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find file: {input_path}")

    with input_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration:
            return [], ["The file was empty."]

        column_map = detect_columns(headers)
        needed_indexes = {column_map["date"], column_map["merchant"], column_map["amount"]}
        if None in needed_indexes:
            warnings.append("I could not confidently find every column, so some rows may be skipped.")

        for line_number, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue
            try:
                cd = column_map["date"]
                cm = column_map["merchant"]
                ca = column_map["amount"]
                if cd is None or cm is None or ca is None:
                    raise ValueError("Row does not have enough columns")
                if max(cd, cm, ca) >= len(row):
                    raise ValueError("Row does not have enough columns")
                date_value = row[cd].strip()
                merchant_value = row[cm].strip()
                amount_value = parse_amount(row[ca])
                if not date_value or not merchant_value:
                    raise ValueError("Date or merchant was blank")
                transactions.append(
                    {
                        "date": date_value,
                        "merchant": merchant_value,
                        "amount": amount_value,
                    }
                )
            except (ValueError, TypeError) as error:
                warnings.append(f"Skipped line {line_number}: {error}")
    return transactions, warnings


def generate_mock_transactions() -> list[dict[str, Any]]:
    """Build a simple demo statement when the user has no CSV yet."""
    today = date.today()
    merchants = [
        ("Starbucks", 6.45),
        ("Starbuks", 5.95),
        ("Whole Foods", 84.20),
        ("Shell Oil", 47.83),
        ("Netflixx", 15.49),
        ("Spotify", 9.99),
        ("Amazon Marketplace", 42.18),
        ("Walgreens", 18.32),
        ("Comcast Cable", 79.99),
        ("Landlord Portal", 1450.00),
        ("Uber Trip", 23.50),
        ("Target", 61.70),
    ]

    transactions: list[dict[str, Any]] = []
    for index, (merchant, amount) in enumerate(merchants):
        transaction_date = today - timedelta(days=index * 2)
        transactions.append(
            {
                "date": transaction_date.isoformat(),
                "merchant": merchant,
                "amount": amount,
            }
        )
    return transactions


def find_best_rule_match(
    merchant: str, rules: dict[str, CategoryRule], threshold: float = 0.76
) -> RuleMatchResult:
    """Try exact-ish matching first, then fuzzy matching."""
    merchant_key = clean_text(merchant)
    best_key: str | None = None
    best_score = 0.0
    best_match_type = "unknown"

    for rule_key, payload in rules.items():
        normalized_rule = clean_text(rule_key)
        if not normalized_rule:
            continue
        if normalized_rule in merchant_key or merchant_key in normalized_rule:
            return cast(
                RuleMatchResult,
                {
                    "category": payload["category"],
                    "subcategory": payload["subcategory"],
                    "confidence": 1.0,
                    "match_type": "exact",
                    "rule_key": rule_key,
                },
            )

        candidate_scores = [similarity_ratio(merchant_key, normalized_rule)]
        for word in merchant_key.split():
            candidate_scores.append(similarity_ratio(word, normalized_rule))
        score = max(candidate_scores)
        if score > best_score:
            best_score = score
            best_key = rule_key
            best_match_type = "fuzzy"

    if best_key is not None and best_score >= threshold:
        payload = rules[best_key]
        return cast(
            RuleMatchResult,
            {
                "category": payload["category"],
                "subcategory": payload["subcategory"],
                "confidence": round(best_score, 3),
                "match_type": best_match_type,
                "rule_key": best_key,
            },
        )

    return cast(
        RuleMatchResult,
        {
            "category": "Unknown",
            "subcategory": "Unknown",
            "confidence": round(best_score, 3),
            "match_type": "unknown",
            "rule_key": "",
        },
    )


def categorize_transactions(
    transactions: list[dict[str, Any]],
    rules: dict[str, CategoryRule] | None = None,
    threshold: float = 0.76,
) -> tuple[list[CategorizedRecord], list[CategorizedRecord]]:
    """Categorize every transaction and return low-confidence items too."""
    active_rules = rules or DEFAULT_RULES.copy()
    categorized: list[CategorizedRecord] = []
    flagged: list[CategorizedRecord] = []

    for transaction in transactions:
        match = find_best_rule_match(str(transaction.get("merchant", "")), active_rules, threshold)
        category = match["category"]
        if category not in VALID_CATEGORIES:
            category = "Unknown"
        sub_raw = str(match["subcategory"]).strip()
        subcategory = sub_raw if sub_raw else category
        try:
            amount = float(transaction["amount"])
        except (KeyError, TypeError, ValueError):
            amount = 0.0
        row = cast(
            CategorizedRecord,
            {
                "date": transaction.get("date", ""),
                "merchant": str(transaction.get("merchant", "")),
                "amount": amount,
                "category": category,
                "subcategory": subcategory,
                "confidence": float(match["confidence"]),
                "match_type": match["match_type"],
            },
        )
        categorized.append(row)

        if row["match_type"] == "fuzzy" and row["confidence"] < min(0.95, threshold + 0.10):
            flagged.append(row)
        elif row["match_type"] == "unknown":
            flagged.append(row)

    return categorized, flagged


def summarize_categories(
    records: list[dict[str, Any]] | Sequence[Mapping[str, Any]],
) -> list[CategorySummaryRow]:
    """Roll transaction data into category totals and counts."""
    summary: dict[str, dict[str, Any]] = {}
    for record in records:
        category = str(record.get("category", "Unknown"))
        try:
            amount = float(record.get("amount", 0.0))
        except (TypeError, ValueError):
            amount = 0.0
        if category not in summary:
            summary[category] = {"category": category, "total": 0.0, "count": 0}
        summary[category]["total"] += amount
        summary[category]["count"] += 1

    rows = list(summary.values())
    rows.sort(key=lambda item: (-float(item["total"]), item["category"]))
    return cast(list[CategorySummaryRow], rows)


def print_rules(rules: dict[str, CategoryRule] | None = None) -> None:
    """Show the rule engine in a readable table."""
    active_rules = rules or DEFAULT_RULES
    print(f"{BLUE}Merchant Rule{' ' * 18}Category{' ' * 12}Subcategory{RESET}")
    print("-" * 68)
    for merchant, payload in sorted(active_rules.items()):
        print(f"{merchant:<30}{payload['category']:<24}{payload['subcategory']}")


def print_summary(records: Sequence[Mapping[str, Any]], flagged: Sequence[Mapping[str, Any]]) -> None:
    """Display sorted summary lines and any transactions needing review."""
    summary_rows = summarize_categories(records)
    print(f"{GREEN}Categorized Summary{RESET}")
    print("-" * 55)
    print(f"{'Category':<22}{'Count':>8}{'Total':>18}")
    print("-" * 55)
    for row in summary_rows:
        print(f"{row['category']:<22}{row['count']:>8}{format_money(row['total']):>18}")

    if flagged:
        print()
        print(f"{YELLOW}Low-confidence / review list{RESET}")
        print("-" * 80)
        print(f"{'Date':<12}{'Merchant':<28}{'Category':<18}{'Confidence':>10}")
        print("-" * 80)
        for item in flagged:
            confidence_text = f"{item['confidence'] * 100:>8.1f}%"
            print(f"{item['date']:<12}{item['merchant'][:27]:<28}{item['category']:<18}{confidence_text:>10}")
    else:
        print()
        print(f"{GREEN}No low-confidence matches needed review.{RESET}")


def add_rule_interactively(rules: dict[str, CategoryRule]) -> None:
    """Let the user add a merchant rule during the menu loop."""
    merchant = input("Merchant name to match: ").strip()
    category = input("Category: ").strip()
    subcategory = input("Subcategory: ").strip()
    if not merchant:
        print(f"{RED}Merchant cannot be blank.{RESET}")
        return
    if category not in VALID_CATEGORIES:
        print(f"{RED}That category is not in the known category set.{RESET}")
        return
    if not subcategory:
        subcategory = category
    rules[clean_text(merchant)] = {"category": category, "subcategory": subcategory}
    print(f"{GREEN}Added rule for {merchant}.{RESET}")


def run_classification(
    file_path: str | Path | None = None,
    use_mock: bool = False,
    threshold: float = 0.76,
    rules: dict[str, CategoryRule] | None = None,
) -> ClassificationResult:
    """Public helper for the unified CLI."""
    active_rules: dict[str, CategoryRule] = (rules or DEFAULT_RULES).copy()
    warnings: list[str] = []

    if use_mock:
        transactions = generate_mock_transactions()
    else:
        if file_path is None:
            raise ValueError("A file path is required unless mock mode is enabled.")
        transactions, warnings = read_transaction_file(file_path)

    categorized, flagged = categorize_transactions(transactions, active_rules, threshold)
    return cast(
        ClassificationResult,
        {
            "records": categorized,
            "flagged": flagged,
            "warnings": warnings,
            "summary": summarize_categories(categorized),
            "rules": active_rules,
        },
    )


def menu() -> None:
    """Run the day-8 interactive interface."""
    rules = DEFAULT_RULES.copy()
    valid_choices = {"1", "2", "3", "4", "5"}
    last_result = None

    while True:
        print()
        print(f"{BLUE}LedgerLogic: Smart Expense Classifier{RESET}")
        print("1. Classify transactions from CSV")
        print("2. Classify built-in mock data")
        print("3. View rules")
        print("4. Add a rule")
        print("5. Quit")
        choice = input("Choose an option: ").strip()

        if choice not in valid_choices:
            print(f"{RED}Please choose one of the menu numbers.{RESET}")
            continue

        if choice == "1":
            file_path = input("CSV path: ").strip()
            try:
                last_result = run_classification(file_path=file_path, rules=rules)
                for warning in last_result["warnings"]:
                    print(f"{YELLOW}{warning}{RESET}")
                print_summary(last_result["records"], last_result["flagged"])
            except (OSError, ValueError, UnicodeError, csv.Error) as error:
                print(f"{RED}Could not classify that file: {error}{RESET}")

        elif choice == "2":
            last_result = run_classification(use_mock=True, rules=rules)
            print_summary(last_result["records"], last_result["flagged"])

        elif choice == "3":
            print_rules(rules)
            if last_result:
                print()
                print(f"Last run had {len(last_result['records'])} categorized transactions.")

        elif choice == "4":
            add_rule_interactively(rules)

        elif choice == "5":
            print("Exiting classifier.")
            break


def main() -> None:
    menu()


if __name__ == "__main__":
    main()
