"""CLI subprocess helper for tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_ledgerlogic_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``python -m ledgerlogic`` from the project root."""
    return subprocess.run(
        [sys.executable, "-m", "ledgerlogic", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
