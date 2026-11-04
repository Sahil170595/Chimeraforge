"""Bounded exact arithmetic for saved GiB and observed MiB; no ambient context."""

from __future__ import annotations

from fractions import Fraction
import re

from chimeraforge.inventory_types import MemoryComparison

MAX_NUMERIC_CHARS = 32
MAX_FRACTION_DIGITS = 6
MAX_MEMORY_MIB = 10**12
MIB_PER_GIB = 1024
SERIALIZATION_HALF_INTERVAL = Fraction(1, 200)
_NUMBER = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?\Z")


def number(text: str) -> Fraction:
    """Admit bounded nonnegative fixed-point input, never exponent expansion."""
    if len(text) > MAX_NUMERIC_CHARS or not _NUMBER.fullmatch(text):
        raise ValueError("unsupported numeric representation")
    value = Fraction(text)
    if value > MAX_MEMORY_MIB:
        raise ValueError("numeric range exceeds observation bounds")
    return value


def decimal_text(value: Fraction) -> str:
    """Render the admitted terminating decimal without Decimal's mutable context."""
    whole, remainder = divmod(value.numerator, value.denominator)
    digits = []
    while remainder:
        remainder *= 10
        digit, remainder = divmod(remainder, value.denominator)
        digits.append(str(digit))
        if len(digits) > MAX_NUMERIC_CHARS:
            raise ValueError("numeric output exceeds bounds")
    return str(whole) + ("." + "".join(digits) if digits else "")


def comparison(mib: str | None, lower: str | None, upper: str | None) -> MemoryComparison:
    if mib is None or lower is None or upper is None:
        return "unknown"
    observed = number(mib) / MIB_PER_GIB
    if observed >= number(upper):
        return "at_least_saved_baseline"
    if observed < number(lower):
        return "below_saved_baseline"
    return "unknown"
