"""
Display precision for report values.

Applied once to every ReportResult (rows, ledger rows and footers) so each
report shows the same precision regardless of how its executor rounded:

- quantity, rate, amount (and their totals / averages): 2 decimals
- FAT and SNF (and their averages): 1 decimal

A trailing marker such as the manual-entry '*' or a '%' sign is kept.
Nested values (e.g. Milk Bill Comparison sides) are left to their templates.
"""

import re
from decimal import Decimal
from typing import Any

from app.modules.reports.application.dto import ReportResult

_TWO_DECIMALS = frozenset({
    "quantity", "total_quantity", "grand_quantity", "net_qty",
    "rate", "average_rate", "grand_rate",
    "amount", "total_amount", "grand_amount",
    "soc_value", "total_soc_value", "net_amount", "total_net_amount",
    "round_diff", "total_round_diff", "ded_advance", "total_ded_advance", "ded_fg", "total_ded_fg",
})
_ONE_DECIMAL = frozenset({
    "fat", "average_fat", "grand_fat",
    "snf", "average_snf", "grand_snf",
})

# Leading number followed by an optional marker suffix: "10.5*", "4.0%", "4.25%*"
_NUMBER_WITH_SUFFIX = re.compile(r"^\s*(-?\d+(?:\.\d+)?)(.*)$")


def _decimals_for(key: str) -> int | None:
    if key in _TWO_DECIMALS:
        return 2
    if key in _ONE_DECIMAL:
        return 1
    return None


def format_value(value: Any, decimals: int) -> Any:
    """Number -> fixed-precision string; marked text keeps its suffix; anything else untouched."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, Decimal)):
        return f"{float(value):.{decimals}f}"
    if isinstance(value, str):
        match = _NUMBER_WITH_SUFFIX.match(value)
        if match:
            return f"{float(match.group(1)):.{decimals}f}{match.group(2)}"
    return value


def _format_mapping(values: dict[str, Any] | None) -> None:
    if not values:
        return
    for key, value in values.items():
        decimals = _decimals_for(key)
        if decimals is not None:
            values[key] = format_value(value, decimals)


def format_report(result: ReportResult) -> ReportResult:
    """Apply display precision in place (row / footer dicts are mutable) and return the result."""
    for row in result.rows or []:
        _format_mapping(row)
    _format_mapping(result.footer)
    for ledger in result.ledger or []:
        for row in ledger.rows or []:
            _format_mapping(row)
        _format_mapping(ledger.footer)
    return result
