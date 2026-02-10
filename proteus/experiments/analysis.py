"""Analysis placeholders for experiment outputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryRow:
    """Minimal summary row type for future analysis outputs."""

    metric: str
    value: float
