"""Interactive analyzer menu."""

from __future__ import annotations

import csv

from ..schemas import CategorizedRecord
from .csv_load import load_categorized_file
from .metrics import run_all_reports
from .mock_data import generate_mock_transactions
from .output import (
    print_anomalies,
    print_day_breakdown,
    print_full_analysis,
    print_monthly_trends,
    print_top_frequency,
    print_top_spend,
)


def menu() -> None:
    """Interactive menu for the analyzer."""
    valid_choices = {"1", "2", "3", "4", "5", "6"}
    current_records: list[CategorizedRecord] = []
    payday_date = 15
    duplicate_records: list[CategorizedRecord] = []

    while True:
        print()
        print("LedgerLogic: Financial Pattern Detector")
        print("1. Run all reports")
        print("2. Run individual report")
        print("3. Generate mock data")
        print("4. Load categorized CSV file")
        print("5. Set payday date")
        print("6. Quit")
        choice = input("Choose an option: ").strip()
        if choice not in valid_choices:
            print("Please choose one of the listed options.")
            continue

        if choice == "1":
            if not current_records:
                current_records = generate_mock_transactions()
                print("No data was loaded yet, so I used built-in mock data.")
            report = run_all_reports(current_records, payday_date=payday_date)
            print_full_analysis(report, duplicate_count=len(duplicate_records))

        elif choice == "2":
            if not current_records:
                current_records = generate_mock_transactions()
                print("No data was loaded yet, so I used built-in mock data.")
            report = run_all_reports(current_records, payday_date=payday_date)
            print("a. Top 10 by frequency")
            print("b. Top 10 by total spend")
            print("c. Day-of-week")
            print("d. Monthly trends")
            print("e. Anomalies")
            inner = input("Pick a report: ").strip().lower()
            if inner == "a":
                print_top_frequency(report["top_by_frequency"])
            elif inner == "b":
                print_top_spend(report["top_by_spend"])
            elif inner == "c":
                print_day_breakdown(report["day_of_week"])
            elif inner == "d":
                print_monthly_trends(report["monthly_trends"])
            elif inner == "e":
                print_anomalies(report["anomaly_report"])
            else:
                print("That report key was not recognized.")

        elif choice == "3":
            current_records = generate_mock_transactions()
            duplicate_records = []
            print(f"Generated {len(current_records)} mock transactions spanning six months.")

        elif choice == "4":
            file_path = input("Categorized CSV path: ").strip()
            try:
                current_records, warnings, duplicate_records = load_categorized_file(file_path)
                for warning in warnings:
                    print(warning)
                print(f"Loaded {len(current_records)} transactions.")
            except (OSError, ValueError, csv.Error) as error:
                print(f"Could not load file: {error}")

        elif choice == "5":
            new_value = input("Payday date (1-28): ").strip()
            if new_value.isdigit() and 1 <= int(new_value) <= 28:
                payday_date = int(new_value)
                print(f"Payday date set to {payday_date}.")
            else:
                print("Please enter a number from 1 to 28.")

        elif choice == "6":
            print("Exiting analyzer.")
            break


def main() -> None:
    menu()


if __name__ == "__main__":
    main()
