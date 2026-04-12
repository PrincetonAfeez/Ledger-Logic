"""Entry point for ``python -m ledgerlogic`` (delegates to :mod:`ledgerlogic.cli`)."""

from __future__ import annotations

from .cli import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
