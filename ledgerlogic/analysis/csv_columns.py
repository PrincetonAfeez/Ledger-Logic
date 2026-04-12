"""Scored column detection for categorized transaction CSV exports."""

from __future__ import annotations

import re
from collections.abc import Callable

from ..textutil import clean_text


def _header_tokens(norm: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", norm))


def _score_date(norm: str, tokens: set[str]) -> float:
    for phrase in (
        "transaction date",
        "posting date",
        "posted date",
        "post date",
        "trans date",
        "value date",
        "book date",
    ):
        if phrase in norm:
            return 14.0
    if norm in {"date", "dt"}:
        return 13.0
    if "date" in tokens:
        return 9.0
    return 0.0


def _score_merchant(norm: str, tokens: set[str]) -> float:
    if norm in {"payee", "merchant", "vendor", "memo", "description", "narration"}:
        return 14.0
    for word in ("payee", "merchant", "vendor", "description", "memo", "narration", "counterparty"):
        if word in norm:
            return 11.0
    hits = tokens & {"payee", "merchant", "vendor", "memo", "description", "narration"}
    if hits:
        return 10.0
    if tokens == {"name"} or (tokens <= {"name", "merchant"} and "name" in tokens):
        return 7.0
    return 0.0


def _score_amount(norm: str, tokens: set[str]) -> float:
    if norm in {"amount", "amt", "debit", "credit"}:
        return 14.0
    if "amount" in tokens:
        return 12.0
    if tokens <= {"debit", "credit", "amount"} and (tokens & {"debit", "credit"}):
        return 10.0
    if norm == "total amount" or ("total" in tokens and "amount" in tokens):
        return 11.0
    if norm == "total" or tokens == {"total"}:
        return 5.0
    return 0.0


def _score_subcategory(norm: str, tokens: set[str]) -> float:
    compact = re.sub(r"[\s_-]+", "", norm)
    if re.fullmatch(r"subcategory|subcat", compact) or "subcategory" in compact:
        return 15.0
    if "sub" in tokens and "category" in tokens:
        return 13.0
    if "sub" in tokens and "cat" in tokens:
        return 10.0
    for phrase in (
        "child category",
        "detail category",
        "line category",
        "secondary category",
        "sub category",
    ):
        if phrase in norm:
            return 12.0
    return 0.0


def _score_category(norm: str, tokens: set[str]) -> float:
    if _score_subcategory(norm, tokens) >= 10.0:
        return 0.0
    for exact in (
        "category",
        "expense category",
        "transaction category",
        "main category",
        "parent category",
        "top category",
        "primary category",
    ):
        if norm == exact:
            return 14.0
    for phrase in ("expense type", "transaction type", "classification"):
        if phrase in norm:
            return 12.0
    if "category" in tokens:
        return 10.0
    if norm == "type" or tokens == {"type"}:
        return 8.0
    if "class" in tokens and "sub" not in tokens:
        return 6.0
    return 0.0


def _pick_column(
    headers_norm: list[str],
    taken: set[int],
    scorer: Callable[[str, set[str]], float],
    *,
    min_score: float,
) -> int | None:
    best_i: int | None = None
    best_s = -1.0
    for i, header in enumerate(headers_norm):
        if i in taken:
            continue
        score = scorer(header, _header_tokens(header))
        if score > best_s:
            best_s = score
            best_i = i
    if best_i is None or best_s < min_score:
        return None
    taken.add(best_i)
    return best_i


def _fallback_slot(preferred: int, column_count: int, taken: set[int]) -> int | None:
    if preferred < column_count and preferred not in taken:
        return preferred
    for j in range(column_count):
        if j not in taken:
            return j
    return None


def detect_columns(headers: list[str]) -> dict[str, int | None]:
    """Map logical fields to column indices using header text, then positional hints.

    Subcategory is detected with higher-priority patterns so plain ``category`` and
    ``subcategory`` / ``sub category`` columns do not collide.
    """
    norm = [clean_text(h) for h in headers]
    n = len(headers)
    taken: set[int] = set()
    mapping: dict[str, int | None] = {
        "date": None,
        "merchant": None,
        "amount": None,
        "category": None,
        "subcategory": None,
    }

    mapping["date"] = _pick_column(norm, taken, _score_date, min_score=5.0)
    mapping["merchant"] = _pick_column(norm, taken, _score_merchant, min_score=5.0)
    mapping["amount"] = _pick_column(norm, taken, _score_amount, min_score=5.0)
    mapping["subcategory"] = _pick_column(norm, taken, _score_subcategory, min_score=9.0)
    mapping["category"] = _pick_column(norm, taken, _score_category, min_score=4.0)

    if mapping["date"] is None and n:
        slot = _fallback_slot(0, n, taken)
        if slot is not None:
            mapping["date"] = slot
            taken.add(slot)
    if mapping["merchant"] is None and n > 1:
        slot = _fallback_slot(1, n, taken)
        if slot is not None:
            mapping["merchant"] = slot
            taken.add(slot)
    if mapping["amount"] is None and n > 2:
        slot = _fallback_slot(2, n, taken)
        if slot is not None:
            mapping["amount"] = slot
            taken.add(slot)
    if mapping["category"] is None and n > 3:
        slot = _fallback_slot(3, n, taken)
        if slot is not None:
            mapping["category"] = slot
            taken.add(slot)

    return mapping
