"""Frequent batch auction mechanism stub."""

from __future__ import annotations

from proteus.mechanisms.base import NullMechanism


class FBAMechanism(NullMechanism):
    """Placeholder FBA implementation for v1 scaffolding."""

    def __init__(self) -> None:
        super().__init__(name="fba")
