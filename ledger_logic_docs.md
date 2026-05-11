# Architecture Decision Record
## App 14 — Ledger Logic Bootstrapper
**Ledger Logic Group | Document 1 of 5**
**Status: Accepted**

---

## Context

Apps 08–13 are independent Ledger Logic modules. App 14 is the unified package that integrates all six into a single importable namespace (`ledgerlogic.*`) and a single CLI (`ledgerlogic` / `python -m ledgerlogic`). It adds three capabilities that no individual module has: (1) a `report_builder.py` that orchestrates all six modules into one cross-module financial summary, (2) a unified argparse CLI with seven subcommands plus a dashboard fallback, and (3) a `choose_records()` routing layer that transparently falls back through file → saved storage → mock data.

---

## Decisions

### Decision 1 — `set_defaults(func=...)` dispatch for seven subcommands

**Chosen:** Each subparser calls `p.set_defaults(func=_handler)`. `main()` routes with `return args.func(args)`. No command → `dashboard_menu()`.

**Rejected:** A chained `if args.command == "import": ...` in `main()`.

**Reason:** The same pattern established in App 07 (DataGuard) and App 13 (Analyzer) reaches its fullest form here with seven subcommands. Adding an eighth subcommand requires one subparser definition and one `set_defaults` call. The `cast(int, args.func(args))` type assertion is the correct way to satisfy the type checker that every `func` returns `int`.

---

### Decision 2 — `choose_records()` three-level fallback

**Chosen:** `choose_records(file_path, use_mock)` tries in order: (1) explicit CSV file via `analyzer.load_categorized_file()`, (2) previously saved categorized transactions via `stored_records_for_analysis()`, (3) mock generator as last resort. Returns `(records, source_label)` — the label is included in the report for traceability.

**Rejected:** Requiring the user to always specify a data source.

**Reason:** The most common workflow is: import once, analyze many times. After the first `ledgerlogic import` run, the categorized CSV is saved to `ledgerlogic_data/`. Every subsequent `analyze`, `budget`, and `report` command should automatically use that saved data without requiring the user to specify it. The fallback hierarchy makes this transparent while still respecting explicit file arguments.

---

### Decision 3 — `report_builder.py` as the cross-module orchestrator

**Chosen:** `build_financial_summary_lines()` imports from `analyzer`, `budget`, `categorizer`, `change_maker`, and `investment` at call time (not at module import). It runs all five modules' core functions on the same set of records and assembles a single multi-section text report.

**Rejected:** Separate CLI commands that the user runs sequentially.

**Reason:** The `ledgerlogic report` command is the culminating feature of the Ledger Logic group — it demonstrates that the six independently developed modules compose into a coherent system. Running them all from a single function with a single dataset ensures all sections of the report describe the same transactions. The deferred imports (`from . import analyzer, budget, ...` inside the function body) prevent circular import issues since `analyzer.py` imports from `categorizer.py` which is in the same package.

---

### Decision 4 — Change-maker integration in the report for the budget-actual gap

**Chosen:** `build_financial_summary_lines()` computes `abs(total_actual - total_budgeted)` and passes the dollar value to `change_maker.calculate_change()`. The breakdown (bills and coins for the gap amount) appears in the Change Snapshot section of the report.

**Rejected:** Showing only the dollar difference in the report.

**Reason:** This is the most creative cross-module connection in the portfolio. The change-maker was built to break down a dollar amount into denominations. Running it on the budget gap produces a visualization that is memorable and demonstrates that the modules are genuinely composable. The `abs()` ensures the change calculator receives a non-negative value regardless of whether spending was over or under budget.

---

### Decision 5 — `analyzer.py` as a stable façade over `ledgerlogic.analysis`

**Chosen:** `analyzer.py` re-exports all public names from `.analysis` via explicit `__all__`. Callers import `from ledgerlogic import analyzer` and call `analyzer.run_all_reports()`.

**Rejected:** Direct imports from `ledgerlogic.analysis` submodules.

**Reason:** App 13 (Analyzer) was built as a standalone module with its own file structure. When integrated into the `ledgerlogic` package, the internal structure moved to `ledgerlogic.analysis.*`. The `analyzer.py` façade provides a stable public name (`ledgerlogic.analyzer.run_all_reports`) that does not change when the internal `analysis` subpackage structure is reorganized. The CLI and `report_builder.py` both import from `analyzer`, not from `analysis`.

---

### Decision 6 — `stored_records_for_analysis()` with date re-parsing

**Chosen:** `stored_records_for_analysis()` loads CSV records via `load_categorized_transactions()` (which returns string dates) and re-parses each `date` field via `parse_date()` before passing records to analytics. Parse failures produce per-row warnings instead of crashing.

**Rejected:** Expecting analytics to handle string dates.

**Reason:** The `records.py` validation layer in `metrics.py` calls `_record_date()` which calls `parse_date()` on string dates — this works. But re-parsing at the load boundary gives cleaner type contracts: `stored_records_for_analysis()` returns records with `date: date` objects, not `date: str`. This makes the records directly comparable by date arithmetic without re-parsing in every metric.

---

### Decision 7 — Seven subcommands mapping to six module areas

**Chosen:** `import`, `analyze`, `change`, `invest`, `budget`, `reconcile`, `report` — seven subcommands covering the six feature modules plus the cross-module report builder.

**Rejected:** A single interactive menu only.

**Reason:** The dashboard `menu()` is available when no subcommand is given. But the argparse CLI enables scripting, CI integration, and piping that the interactive menu cannot support. `ledgerlogic report --mock > report.txt` is a one-liner that produces the full financial summary. The two interfaces coexist — `dashboard_menu()` is the fallback, argparse is the scriptable surface.

---

## Consequences

**Positive:**
- `set_defaults(func=...)` dispatch scales to additional subcommands with no main() changes.
- `choose_records()` fallback makes the common workflow (import once, analyze many) transparent.
- `report_builder.py` demonstrates composability across all six modules.
- Change-maker integration in the budget gap section is the most creative cross-module use in the portfolio.
- `analyzer.py` façade provides a stable import name insulated from internal package restructuring.

**Negative / Trade-offs:**
- `build_financial_summary_lines()` deferred imports (`from . import analyzer, budget, ...`) add a small startup cost on first report call.
- The budget section of the report uses hardcoded `starter_categories()` rather than a saved budget profile. A user who has customized their categories will not see their customizations in the report.
- `dashboard_menu()` option 7 (Generate full report) uses hardcoded defaults (`income=5000, rate=7.0, years=20`). These should come from config.

---

*Constitution reference: Articles 1, 2, 3. Amendment 1.2 (Group D) equivalent: the package monorepo DRY structure is an architectural feature.*


---


# Technical Design Document
## App 14 — Ledger Logic Bootstrapper
**Ledger Logic Group | Document 2 of 5**

---

## Overview

The Ledger Logic Bootstrapper is the unified `ledgerlogic` package — it integrates Apps 08–13 into a single installable namespace and provides a seven-subcommand CLI plus dashboard, plus a `report_builder` that orchestrates all six modules into one cross-module summary.

**Files:** `cli.py` (375 lines), `report_builder.py`, `analyzer.py` (façade), `__init__.py`, `__main__.py`
**Submodules:** `budget`, `categorizer`, `change_maker`, `investment`, `reconciler`, `analysis` (analyzer), `report_builder`
**Shared (canonical):** `parsing.py`, `schemas.py`, `storage.py`, `textutil.py`
**Entry points:** `ledgerlogic` → `cli.main()`, `python -m ledgerlogic` → `__main__.main()`
**Dependencies:** All six module dependencies (stdlib only)

---

## Package Structure

```
ledgerlogic/
├── __init__.py          # Namespace + __all__
├── __main__.py          # python -m ledgerlogic → cli.main()
├── cli.py               # Unified CLI (375 lines)
├── report_builder.py    # Cross-module orchestrator
├── analyzer.py          # Stable façade over .analysis
├── analysis/            # App 13 internals (metrics, csv_load, etc.)
│   ├── __init__.py
│   ├── metrics.py
│   ├── csv_columns.py
│   ├── csv_load.py
│   ├── records.py
│   ├── mock_data.py
│   ├── output.py
│   ├── menu.py
│   └── config.py
├── budget.py            # App 08
├── categorizer.py       # App 11 (with relative imports)
├── change_maker.py      # App 09
├── investment.py        # App 10 entry point (re-exports)
├── reconciler.py        # App 12
├── parsing.py           # Shared (canonical)
├── schemas.py           # Shared (canonical)
├── storage.py           # Shared (canonical)
└── textutil.py          # Shared (canonical)
```

---

## CLI Subcommand Map

```
ledgerlogic
├── import       → import_statement()     → categorizer.run_classification() → save_categorized_transactions()
├── analyze      → analyze_spending()     → choose_records() → analyzer.run_all_reports() → print_full_analysis()
├── change       → make_change()          → change_maker.calculate_change() → print_change_result()
├── invest       → run_investment_projection() → investment.project_scenario() → format_single_projection()
├── budget       → run_budget()           → budget.allocate_*() + compare_actual_to_budget()
├── reconcile    → run_reconcile()        → reconciler.run_reconciliation()
├── report       → build_report()         → choose_records() → report_builder.write_full_financial_report()
└── (no args)    → dashboard_menu()       → interactive 8-option loop delegating to module menus
```

---

## `choose_records()` Fallback Chain

```python
def choose_records(file_path=None, use_mock=False):
    if use_mock:
        return analyzer.generate_mock_transactions(), "built-in mock data"
    if file_path:
        records, warnings, duplicates = analyzer.load_categorized_file(file_path)
        return records, str(file_path)
    saved, load_warnings = stored_records_for_analysis()
    if saved:
        return saved, str(get_categorized_path())
    return analyzer.generate_mock_transactions(), "built-in mock data because no saved import was found"
```

---

## `report_builder.py` Cross-Module Orchestration

```python
def build_financial_summary_lines(records, source_label, params):
    from . import analyzer, budget, categorizer, change_maker, investment

    # 1. Spending analysis
    spend_report = analyzer.run_all_reports(records, payday_date=params["payday"])
    category_summary = categorizer.summarize_categories(shaped_records)

    # 2. Budget comparison (50/30/20 vs actual)
    actuals = budget.aggregate_actual_spending(records)
    budget_plan = budget.allocate_fifty_thirty_twenty(params["income"], budget.starter_categories())
    budget_comparison = budget.compare_actual_to_budget(budget_plan, actuals)

    # 3. Investment projection
    scenario = investment.default_scenario("Report Projection")
    scenario.update({"contribution_amount": params["monthly"], ...})
    investment_result = investment.project_scenario(scenario)

    # 4. Change-maker on budget gap
    net_gap = abs(budget_comparison["total_actual"] - budget_comparison["total_budgeted"])
    change_result = change_maker.calculate_change(f"{net_gap:.2f}")

    # Assemble sections into lines list
```

### Report Sections

| Section | Module called | Key output |
|---|---|---|
| Report header | — | Source label, record count |
| Spending snapshot | `analyzer` | Top category, top merchant, weekend %, anomaly count |
| Budget snapshot | `budget` | Budget vs actual, top overages |
| Investment snapshot | `investment` | 20yr projection, inflation-adjusted balance |
| Change snapshot | `change_maker` | Bill/coin breakdown of budget gap |

---

## `stored_records_for_analysis()`

```python
def stored_records_for_analysis():
    saved, csv_warnings = load_categorized_transactions()  # string dates from CSV
    for row in saved:
        parsed.append({
            "date": parse_date(str(row["date"])),           # re-parse to date object
            "merchant": row["merchant"],
            "amount": float(row["amount"]),
            "category": row["category"],
            "subcategory": row.get("subcategory", row["category"]),
        })
    return parsed, warnings
```

---

## `FinancialReportParams` Schema

```python
{
    "payday": int,          # Day of month for pre/post payday split
    "income": float,        # Monthly income assumption for budget
    "monthly": float,       # Monthly investment contribution
    "rate": float,          # Annual interest rate (%)
    "years": int,           # Investment projection length
    "inflation": float,     # Inflation rate (%)
    "output": str | None,   # Output path for report text file (None = default)
}
```

---

## Dashboard Menu

```
LedgerLogic CLI
1. Import and categorize transactions  → categorizer.menu()
2. Analyze spending patterns           → analyzer.menu()
3. Calculate change                    → change_maker.menu()
4. Project investments                 → investment.menu()
5. Build a budget                      → budget.menu()
6. Reconcile two files                 → reconciler.menu()
7. Generate full report                → build_report(hardcoded_defaults)
8. Quit
```


---


# Interface Design Specification
## App 14 — Ledger Logic Bootstrapper
**Ledger Logic Group | Document 3 of 5**

---

## CLI Reference

### `ledgerlogic import`
```bash
# Import and categorize a CSV statement
ledgerlogic import transactions.csv

# Use mock data
ledgerlogic import --mock

# Custom fuzzy threshold (default 76%)
ledgerlogic import transactions.csv --threshold 80

# Custom output path
ledgerlogic import transactions.csv --output categorized.csv
```

### `ledgerlogic analyze`
```bash
# Analyze saved categorized data (auto-loaded from ledgerlogic_data/)
ledgerlogic analyze

# Analyze specific file
ledgerlogic analyze categorized.csv

# Use mock data
ledgerlogic analyze --mock

# Custom payday
ledgerlogic analyze --payday 1
```

### `ledgerlogic change`
```bash
ledgerlogic change 47.63
ledgerlogic change 4763       # raw cents mode
ledgerlogic change 47.63 --verbose   # show greedy trace
```

### `ledgerlogic invest`
```bash
# Quick projection with defaults
ledgerlogic invest

# Custom scenario
ledgerlogic invest --principal 50000 --rate 8 --years 30 --monthly 500

# With chart
ledgerlogic invest --principal 10000 --chart

# Save scenario
ledgerlogic invest --name "Retirement" --principal 25000 --save

# Compare saved scenarios
ledgerlogic invest --compare-saved
```

### `ledgerlogic budget`
```bash
# 50/30/20 budget for $5000 income
ledgerlogic budget --income 5000

# All three strategies
ledgerlogic budget --income 5000 --strategy all

# Compare with imported spending
ledgerlogic budget --income 5000 --compare-actuals

# Save budget profile
ledgerlogic budget --income 5000 --save
```

### `ledgerlogic reconcile`
```bash
# Compare two files
ledgerlogic reconcile bank.csv ledger.csv

# Mock data
ledgerlogic reconcile --mock

# Custom thresholds
ledgerlogic reconcile bank.csv ledger.csv --fuzzy 85 --date-tolerance 1

# Export report
ledgerlogic reconcile bank.csv ledger.csv --export
```

### `ledgerlogic report`
```bash
# Full report with default assumptions
ledgerlogic report

# Custom financial parameters
ledgerlogic report --income 6000 --monthly 300 --rate 8 --years 30

# Save to file
ledgerlogic report --output my_report.txt

# Use mock data
ledgerlogic report --mock
```

### Dashboard (no subcommand)
```bash
ledgerlogic       # Opens interactive 8-option menu
python -m ledgerlogic
```

---

## Public API

### Library Use

```python
from ledgerlogic import analyzer, budget, categorizer, change_maker, investment, reconciler
from ledgerlogic.report_builder import write_full_financial_report, build_financial_summary_lines
from ledgerlogic.cli import choose_records, stored_records_for_analysis

# Standard workflow
records, source = choose_records(file_path="categorized.csv")
report = analyzer.run_all_reports(records, payday_date=15)
```

---

## `FinancialReportParams` Usage

```python
params: FinancialReportParams = {
    "payday": 15,
    "income": 5000.0,
    "monthly": 200.0,
    "rate": 7.0,
    "years": 20,
    "inflation": 2.5,
    "output": None,
}
report_text, output_path = write_full_financial_report(records, "my_data.csv", params)
```

---

## Report Output Format

```
LedgerLogic Financial Summary
================================
Data source: ledgerlogic_data/categorized_transactions.csv
Transactions analyzed: 78

Spending snapshot
--------------------------------
Top category: Housing at $8,700.00
Top merchant by spend: Landlord Portal at $8,700.00
Weekend vs weekday average difference: 18.2%
Anomalies flagged: 1

Budget snapshot
--------------------------------
Income assumption: $5,000.00
Budgeted total: $5,000.00
Actual categorized spend: $9,543.21
Total overage: $4,543.21
Total surplus: $0.00
Over budget: Housing at n/a (unbudgeted) ($4,700.00 over)

Investment snapshot
--------------------------------
20-year projection at 7.00% with $200.00 monthly contributions
Projected ending balance: $94,035.79
Inflation-adjusted ending balance: $63,214.18
Purchasing power loss estimate: $30,821.61

Change snapshot
--------------------------------
Absolute budget vs actual gap (cash denomination breakdown): $4,543.21
$100 bill: 45
$20 bill: 2
$1 bill: 3
dime: 2
penny: 1

Saved report path: /path/to/ledgerlogic_data/ledgerlogic_report.txt
```

---

## Seven Subcommand Flags Summary

| Subcommand | Required | Optional |
|---|---|---|
| `import` | file (or --mock) | --threshold, --output |
| `analyze` | — | file, --mock, --payday |
| `change` | amount | --verbose |
| `invest` | — | --name, --principal, --monthly, --rate, --years, --compounding, --timing, --inflation, --chart, --save, --compare-saved |
| `budget` | --income | --strategy, --compare-actuals, --save |
| `reconcile` | source + reference (or --mock) | --fuzzy, --date-tolerance, --amount-tolerance, --export, --output-dir |
| `report` | — | --income, --monthly, --rate, --years, --inflation, --payday, --mock, --output |


---


# Runbook
## App 14 — Ledger Logic Bootstrapper
**Ledger Logic Group | Document 4 of 5**

---

## Requirements

- Python 3.11 or later (for `tomllib` in `analysis/config.py`)
- No third-party dependencies for basic use
- `typing_extensions` for `schemas.py` (Python < 3.11 `NotRequired`)

---

## Installation

### From repo (development)
```bash
git clone https://github.com/PrincetonAfeez/ledger-logic
cd ledger-logic
pip install -e .
ledgerlogic version
```

### Without pip install
```bash
cd ledger-logic
python -m ledgerlogic
```

---

## Quick Start Workflow

### Step 1 — Import a CSV statement
```bash
ledgerlogic import my_bank_export.csv
# Saved categorized transactions to ledgerlogic_data/categorized_transactions.csv
```

### Step 2 — Analyze spending patterns
```bash
ledgerlogic analyze
# Automatically loads from ledgerlogic_data/
```

### Step 3 — Generate full report
```bash
ledgerlogic report --income 5000
# Prints full report and saves to ledgerlogic_data/ledgerlogic_report.txt
```

---

## Using the Dashboard
```bash
ledgerlogic
# Opens:
# LedgerLogic CLI
# 1. Import and categorize transactions
# 2. Analyze spending patterns
# ...
# 8. Quit
```

---

## Using as a Library

### Basic workflow
```python
from ledgerlogic import analyzer, budget
from ledgerlogic.cli import choose_records

records, source = choose_records()  # auto-loads from storage
report = analyzer.run_all_reports(records, payday_date=15)
allocation = budget.allocate_fifty_thirty_twenty(5000.0, budget.starter_categories())
```

### Generate the full report programmatically
```python
from ledgerlogic.report_builder import write_full_financial_report
from ledgerlogic.cli import choose_records
from ledgerlogic.schemas import FinancialReportParams

records, source = choose_records()
params: FinancialReportParams = {
    "payday": 15, "income": 5000.0, "monthly": 200.0,
    "rate": 7.0, "years": 20, "inflation": 2.5, "output": None
}
text, path = write_full_financial_report(records, source, params)
print(f"Report: {path}")
```

### Import all six module APIs
```python
from ledgerlogic import (
    analyzer, budget, categorizer, change_maker, investment, reconciler
)
```

---

## Setting the Data Directory

```bash
# Default: ./ledgerlogic_data/
export LEDGERLOGIC_DATA_DIR=/home/user/.ledgerlogic
ledgerlogic import transactions.csv
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'ledgerlogic'`
Either install with `pip install -e .` from the repo root, or run `python -m ledgerlogic` from the `ledgerlogic/` parent directory.

### `analyze` shows mock data instead of my import
The saved categorized CSV was not found in `ledgerlogic_data/`. Confirm the `import` command ran successfully and check `ledgerlogic_data/categorized_transactions.csv` exists. Or set `LEDGERLOGIC_DATA_DIR` to a stable path.

### Report budget section shows only `starter_categories()`
The report uses `starter_categories()` with `allocate_fifty_thirty_twenty()` as a baseline. Custom budget profiles are not yet loaded by the report builder. Use `ledgerlogic budget --compare-actuals` for a comparison that includes your saved budget profile.

### `tomllib` not found
Ensure Python 3.11+. On 3.10: `pip install tomli` and patch `config.py` to `import tomli as tomllib`.


---


# Lessons Learned
## App 14 — Ledger Logic Bootstrapper
**Ledger Logic Group | Document 5 of 5**

---

## Why This Design Was Chosen

The `choose_records()` fallback chain emerged from thinking about how the tool would actually be used. The first version of `ledgerlogic analyze` required `--csv categorized.csv` every time. After the third time running that flag manually, the right design became obvious: save once, use many times. The three-level fallback (explicit file → saved file → mock) encodes the most common usage pattern as the default behavior, without removing the ability to override.

The cross-module report was the most architecturally challenging feature. The first version of `build_financial_summary_lines()` imported all six modules at the top of `report_builder.py`. This produced a circular import: `report_builder.py` imports `budget.py`, which imports `schemas.py`, which `report_builder.py` also imports — and `categorizer.py` imports `analysis.csv_columns` via a lazy import, which itself imports `textutil.py`. Moving the module imports inside the function body resolved all circular import issues by deferring them until the function is actually called.

---

## What Was Intentionally Omitted

**Saved budget profile integration in the report:** `build_financial_summary_lines()` uses `starter_categories()` as the budget baseline rather than loading a saved profile. Loading a saved profile requires a schema version check (the budget profile JSON format is not yet versioned) and potentially migrating old formats. This was deferred to keep the report builder simple.

**Authentication or user accounts:** LedgerLogic stores data in `ledgerlogic_data/` without any access controls. Multiple users on the same machine would share the same data directory. Multi-user support would require either per-user directories (e.g., `~/.ledgerlogic/`) or an authentication layer.

**Web interface:** The dashboard is a terminal text menu. A Flask or FastAPI web front-end would make the tool accessible to non-technical users. Deferred as out of scope for the academic portfolio.

**Plugin-style module registration:** Adding a seventh feature module currently requires edits to `cli.py` (subparser + handler), `__init__.py` (namespace), and `report_builder.py` (if the module contributes to the report). A plugin system where modules self-register would eliminate these manual steps, but was not implemented at this scale.

---

## Biggest Weakness

The `run_budget()` function in `cli.py` builds the budget categories from `starter_categories()` rather than from the user's saved budget profile. This means the budget analysis in the CLI always uses the default category weights and tiers, not the customized ones the user may have set interactively via `ledgerlogic budget`. The disconnect between the CLI budget analysis and the interactive budget customization is the most significant UX gap in the bootstrapper.

The fix would be: `load_json(get_budget_profile_path(), default={})` → reconstruct `categories` from the saved profile if present → fall back to `starter_categories()` otherwise. A budget profile JSON format specification (analogous to the investment `SCHEMA_VERSION` marker) would need to be established first.

---

## Scaling Considerations

**If the module count grows to ten or more:** The `set_defaults(func=...)` dispatch scales cleanly — one subparser per module, no changes to `main()`. The `report_builder.py` would need a new section per module. The `dashboard_menu()` would need new numbered options. Neither is architecturally difficult.

**If data grows to millions of transactions:** The `choose_records()` fallback materializes all records in memory. A streaming architecture — `csv.reader` as a generator, metrics computed iteratively — would handle large files. The `load_categorized_transactions()` function in `storage.py` would need to yield rows rather than accumulate them.

**If the package becomes publicly installable:** The hardcoded defaults in `run_investment_projection()` and `dashboard_menu()` option 7 (`income=5000, rate=7.0`) should come from config. Adding `ledgerlogic.config` (analogous to App 13's `config.py`) would give users a persistent defaults file without requiring command-line flags every run.

---

## What This Project Taught

**Circular imports are resolved by deferred imports.** The `from . import analyzer, budget, ...` inside the function body in `report_builder.py` is not a hack — it is the standard Python pattern for breaking circular import chains. Putting imports inside function bodies delays their execution until the function is called, by which point all modules have finished their own top-level initialization. Understanding when to use module-level imports vs function-level imports is a packaging skill.

**A fallback chain is a user experience decision.** `choose_records()` is three lines of if-else, but it encodes a complete mental model of how the tool will be used. Writing it forced the question: "what should happen when the user doesn't say where their data is?" The answer (try the last import, then mock) is a design decision that shapes every subsequent user interaction with the tool.

**The `report` command is proof of composability.** The cross-module report works because every module's `run()` function accepts the same kind of input (categorized records as dicts) and produces structured output (TypedDict). The shared `schemas.py` TypedDict contracts that seemed like overhead on App 08 become the enabling infrastructure on App 14. The final report is possible only because every module honors the contract.

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation) for App 14.*
*Group B — Ledger Logic: Documentation complete.*
