"""Optimal change calculator.

Denominations are a simplified common US cash drawer (no half-dollar or $1 coin).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import cast

from .schemas import ChangeResult, GreedyTraceStep, ParsedAmountToCents
from .storage import format_money

DENOMINATIONS: dict[int, dict[str, str]] = {
    10000: {"name": "$100 bill", "type": "bill"},
    5000: {"name": "$50 bill", "type": "bill"},
    2000: {"name": "$20 bill", "type": "bill"},
    1000: {"name": "$10 bill", "type": "bill"},
    500: {"name": "$5 bill", "type": "bill"},
    100: {"name": "$1 bill", "type": "bill"},
    25: {"name": "quarter", "type": "coin"},
    10: {"name": "dime", "type": "coin"},
    5: {"name": "nickel", "type": "coin"},
    1: {"name": "penny", "type": "coin"},
}


def parse_amount_to_cents(amount_text: str) -> ParsedAmountToCents:
    """Parse user input to whole cents (sub-cent values round half away from zero).

    **Dollar amounts:** ``14.73``, ``$14.73``, ``$1,234.56``, or ``+2.50``.

    **Integer-only strings (no ``$`` in the original input):**

    - More than two digits → **total cents** (e.g. ``1473`` means 14 dollars and 73 cents).
    - At most two digits → **whole dollars** (e.g. ``5`` means five dollars; ``12`` means twelve).

    If ``$`` appeared anywhere, an all-digit run is always **whole dollars**
    (e.g. ``$1473`` means 1473 dollars, not 14.73).

    Scientific notation is not accepted.
    """
    original = (amount_text or "").strip()
    if not original:
        raise ValueError("Please enter an amount.")

    had_dollar_symbol = "$" in original
    cleaned = original.replace("$", "").replace(",", "").strip()
    if cleaned.startswith("+"):
        cleaned = cleaned[1:].strip()
    if cleaned.startswith("-"):
        raise ValueError("Negative amounts are not allowed for change making.")
    if not cleaned:
        raise ValueError("Please enter an amount.")
    if "e" in cleaned.lower():
        raise ValueError(
            "Scientific notation is not supported. Use a plain amount like 14.73 or $14.73."
        )

    try:
        if "." in cleaned:
            decimal_amount = Decimal(cleaned)
            rounded = decimal_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cents = int(rounded * 100)
            rounded_happened = decimal_amount != rounded
            dollars = float(rounded)
        elif cleaned.isdigit():
            if had_dollar_symbol or len(cleaned) <= 2:
                decimal_amount = Decimal(cleaned)
                rounded = decimal_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                cents = int(rounded * 100)
                rounded_happened = False
                dollars = float(rounded)
            else:
                cents = int(cleaned)
                rounded_happened = False
                dollars = cents / 100
        else:
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValueError("That amount was not numeric. Try formats like 14.73, $14.73, or 1473.") from None

    return cast(
        ParsedAmountToCents,
        {
            "input_text": original,
            "cents": cents,
            "dollars": dollars,
            "rounded": rounded_happened,
        },
    )


def calculate_change(amount_text: str, verbose: bool = False) -> ChangeResult:
    """Run the greedy algorithm using integer cents internally."""
    parsed = parse_amount_to_cents(amount_text)
    cents = parsed["cents"]

    if cents == 0:
        return cast(
            ChangeResult,
            {
                "ok": True,
                "cents": 0,
                "amount": 0.0,
                "rounded": parsed["rounded"],
                "breakdown": {},
                "trace": [],
                "bill_count": 0,
                "coin_count": 0,
                "verification": 0.0,
                "used_denominations": set[int](),
                "unused_denominations": set(DENOMINATIONS.keys()),
                "message": "Zero dollars means there is no change to hand back.",
            },
        )

    remaining = cents
    breakdown: dict[int, int] = {}
    trace: list[GreedyTraceStep] = []
    used_denominations: set[int] = set()

    for value in sorted(DENOMINATIONS, reverse=True):
        info = DENOMINATIONS[value]
        count = remaining // value
        leftover = remaining % value
        if count:
            breakdown[value] = count
            used_denominations.add(value)
        if verbose:
            trace.append(
                cast(
                    GreedyTraceStep,
                    {
                        "denomination": value,
                        "name": info["name"],
                        "before": remaining,
                        "count": int(count),
                        "after": int(leftover),
                    },
                )
            )
        remaining = leftover

    unused_denominations = set(DENOMINATIONS.keys()) - used_denominations
    bill_count = 0
    coin_count = 0
    verification_cents = 0
    for value, count in breakdown.items():
        verification_cents += value * count
        if DENOMINATIONS[value]["type"] == "bill":
            bill_count += count
        else:
            coin_count += count

    return cast(
        ChangeResult,
        {
            "ok": True,
            "cents": cents,
            "amount": parsed["dollars"],
            "rounded": parsed["rounded"],
            "breakdown": breakdown,
            "trace": trace,
            "bill_count": bill_count,
            "coin_count": coin_count,
            "verification": verification_cents / 100,
            "used_denominations": used_denominations,
            "unused_denominations": unused_denominations,
            "message": "",
        },
    )


def print_denomination_info() -> None:
    """Show the supported US denominations."""
    print("Supported denominations")
    print("-" * 40)
    for value in sorted(DENOMINATIONS, reverse=True):
        info = DENOMINATIONS[value]
        display_value = format_money(value / 100)
        print(f"{display_value:<10}{info['name']:<14}{info['type']}")


def print_change_result(result: ChangeResult, verbose: bool = False) -> None:
    """Display the change result in separate bill and coin sections."""
    if result["message"]:
        print(result["message"])
        return

    if result["rounded"]:
        print("Note: the input was rounded to the nearest cent before processing.")

    print(f"Change for {format_money(result['amount'])}")
    print("-" * 48)
    print("Bills")
    print(f"{'Denomination':<18}{'Count':>8}{'Subtotal':>16}")
    print("-" * 48)
    for value in sorted(result["breakdown"], reverse=True):
        if DENOMINATIONS[value]["type"] != "bill":
            continue
        count = result["breakdown"][value]
        print(f"{DENOMINATIONS[value]['name']:<18}{count:>8}{format_money((value * count) / 100):>16}")

    print()
    print("Coins")
    print(f"{'Denomination':<18}{'Count':>8}{'Subtotal':>16}")
    print("-" * 48)
    for value in sorted(result["breakdown"], reverse=True):
        if DENOMINATIONS[value]["type"] != "coin":
            continue
        count = result["breakdown"][value]
        print(f"{DENOMINATIONS[value]['name']:<18}{count:>8}{format_money((value * count) / 100):>16}")

    print()
    print(f"Total bills used: {result['bill_count']}")
    print(f"Total coins used: {result['coin_count']}")
    print(f"Verification: {format_money(result['verification'])} adds back to the original amount.")
    print(f"Unused denominations this time: {', '.join(DENOMINATIONS[value]['name'] for value in sorted(result['unused_denominations'], reverse=True))}")

    if verbose and result["trace"]:
        print()
        print("Greedy trace")
        print(f"{'Step':<4}{'Denomination':<18}{'Before':>10}{'Used':>8}{'Left':>10}")
        print("-" * 60)
        for index, step in enumerate(result["trace"], start=1):
            before = format_money(step["before"] / 100)
            after = format_money(step["after"] / 100)
            print(f"{index:<4}{step['name']:<18}{before:>10}{step['count']:>8}{after:>10}")


def menu() -> None:
    """Interactive loop for the change maker."""
    verbose = True
    valid_choices = {"1", "2", "3", "4"}

    while True:
        print()
        print("LedgerLogic: Optimal Change Calculator")
        print("1. Calculate change")
        print("2. Toggle verbose mode")
        print("3. View denomination info")
        print("4. Quit")
        choice = input("Choose an option: ").strip()
        if choice not in valid_choices:
            print("Please pick one of the listed menu options.")
            continue

        if choice == "1":
            amount_text = input("Amount: ").strip()
            try:
                result = calculate_change(amount_text, verbose=verbose)
                print_change_result(result, verbose=verbose)
            except ValueError as error:
                print(error)

        elif choice == "2":
            verbose = not verbose
            mode = "verbose" if verbose else "quiet"
            print(f"Mode is now {mode}.")

        elif choice == "3":
            print_denomination_info()

        elif choice == "4":
            print("Exiting change maker.")
            break


def main() -> None:
    menu()


if __name__ == "__main__":
    main()
