# Schema folder for LedgerLogic

This folder contains a simple set of standalone JSON Schema files based on the public data contracts in the repository's `schemas.py` module.

## Included files

- `common.schema.json` — shared enums and reusable definitions
- `category_rule.schema.json`
- `categorized_record.schema.json`
- `classification_result.schema.json`
- `analysis_report.schema.json`
- `change_result.schema.json`
- `investment_scenario.schema.json`
- `projection_result.schema.json`
- `budget_allocation.schema.json`
- `budget_comparison_result.schema.json`
- `reconciliation_report.schema.json`
- `manifest.json`

## Notes

- These schemas are intentionally lightweight and practical.
- Python `date` values are represented as JSON strings using `YYYY-MM-DD`.
- Python `set[...]` values are represented as JSON arrays with `uniqueItems: true`.
- The repository already exposes TypedDict contracts through `ledgerlogic.schemas`; this folder makes them easier to consume from tools, docs, and external validators.

## Suggested placement

Add this folder at the repository root as:

```text
Ledger-Logic/
└── Schema/
    ├── common.schema.json
    ├── categorized_record.schema.json
    └── ...
```
