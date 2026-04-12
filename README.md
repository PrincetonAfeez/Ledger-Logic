# LedgerLogic

Personal finance CLI: import and categorize CSV statements, analyze spending, budget, reconcile two files, project investments, and generate text reports.

## Install

```bash
pip install -e .
```

Development (tests):

```bash
pip install -e ".[dev]"
ruff check ledgerlogic tests
mypy ledgerlogic
pytest
```

GitHub Actions (`.github/workflows/ci.yml`) runs **ruff**, **mypy**, and **pytest** on Python 3.10 and 3.12 when you push to GitHub.

## Usage

```bash
ledgerlogic --help
ledgerlogic import path/to/statement.csv
ledgerlogic analyze
ledgerlogic report
```

Run `ledgerlogic` with no arguments for the interactive menu.

The argparse implementation and dashboard live in **`ledgerlogic.cli`**; `python -m ledgerlogic` loads `ledgerlogic.__main__`, which delegates to `cli.main`.

## Package layout

Importable submodules include **`analysis`** (CSV load, metrics, menus), **`analyzer`** (stable façade over `analysis`), **`budget`**, **`categorizer`**, **`change_maker`**, **`investment`**, **`parsing`**, **`reconciler`**, **`report_builder`**, **`schemas`**, **`storage`**, **`textutil`**, and **`cli`**. See `ledgerlogic.__all__` for the canonical list.

## CSV data paths

- **`ledgerlogic.analyzer.load_categorized_file`** (and **`analysis.csv_load`**) — load a categorized export with validation and duplicate detection (typical **analyze** / **report** path from a file argument).
- **`ledgerlogic.storage.load_categorized_transactions`** — read the **saved** `categorized_transactions.csv` under the data directory (used by **budget** and by **`cli.stored_records_for_analysis`**). Amounts use the same **`parsing.parse_amount`** rules as elsewhere.

## Assumptions

Defaults are **US-oriented**: date parsing favors **US month/day** for ambiguous slashes (see **`parsing.parse_date`**), amounts are **USD-style**, and **change** uses a simplified **US bill/coin** set. Investment and budget math use **nominal** dollars unless noted (e.g. inflation-adjusted lines in projections).

## Data directory

By default, files are read and written under `./ledgerlogic_data` in the current working directory. Set **`LEDGERLOGIC_DATA_DIR`** to use a fixed folder (for example your user profile or a synced drive).

## Requirements

Python 3.10+

## Library note

`ledgerlogic.storage.load_categorized_transactions` returns a tuple ``(records, warnings)`` so callers can surface CSV parse issues.

Shared **TypedDict** shapes for major payloads live in `ledgerlogic.schemas` (e.g. `ClassificationResult`, `AnalysisReport`, `ChangeResult`, `InvestmentScenario`). Import feature modules by name (e.g. `from ledgerlogic import storage, parsing`) without pulling in the full CLI until you import **`cli`**.
