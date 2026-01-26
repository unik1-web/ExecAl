from __future__ import annotations

from decimal import Decimal


def compute_deviation(value: Decimal | None, ref_min: Decimal | None, ref_max: Decimal | None) -> str | None:
    if value is None or ref_min is None or ref_max is None:
        return None
    if value < ref_min:
        return "low"
    if value > ref_max:
        return "high"
    return "normal"

