"""Numeric formatting for report values.

Rounding happens once, here, on the way into the report payload. The template
formats units and signs for display; this module only makes sure the numbers
handed over are stable and reproducible.
"""

from __future__ import annotations

#: Decimal places per quantity kind.
LOADING_DECIMALS = 1  # 91.4 %
VOLTAGE_DECIMALS = 3  # 0.978 p.u.
DELTA_LOADING_DECIMALS = 1  # +14.3 %-Pkt.
DELTA_VOLTAGE_DECIMALS = 3  # -0.017 p.u.


def round_loading(value: float | None) -> float | None:
    return None if value is None else round(float(value), LOADING_DECIMALS)


def round_voltage(value: float | None) -> float | None:
    return None if value is None else round(float(value), VOLTAGE_DECIMALS)


def round_for_unit(value: float | None, unit: str) -> float | None:
    """Round according to the unit carried by the row."""
    if value is None:
        return None
    if unit == "%":
        return round_loading(value)
    if unit == "p.u.":
        return round_voltage(value)
    return round(float(value), 3)
