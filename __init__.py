"""LedgerLogic: personal finance CLI and importable modules.

Package sources live at the repository root (see ``pyproject.toml``); import paths
still use the ``ledgerlogic.*`` namespace.

The unified command line lives in :mod:`ledgerlogic.cli`; run ``ledgerlogic`` or
``python -m ledgerlogic`` to start it. Feature areas are split into submodules
(:mod:`categorizer`, :mod:`budget`, :mod:`investment`, etc.). Shared contracts
are in :mod:`ledgerlogic.schemas`; I/O helpers in :mod:`ledgerlogic.storage`;
date/amount parsing in :mod:`ledgerlogic.parsing`; text normalization in
:mod:`ledgerlogic.textutil`. Spending analysis also exposes :mod:`ledgerlogic.analysis`
and a stable façade :mod:`ledgerlogic.analyzer`.
"""

__all__ = [
    "analysis",
    "analyzer",
    "budget",
    "categorizer",
    "change_maker",
    "cli",
    "investment",
    "parsing",
    "reconciler",
    "report_builder",
    "schemas",
    "storage",
    "textutil",
]
