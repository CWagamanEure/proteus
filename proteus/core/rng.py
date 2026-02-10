"""Deterministic RNG stream manager."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field


def _hash_to_u64(text: str) -> int:
    digest = hashlib.sha256(text.encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def derive_repetition_seed(base_seed: int, repetition: int) -> int:
    """
    derive a stable per-repetition seed from one scenario seed.
    """
    if repetition < 0:
        raise ValueError("repetition must be non-negative")
    return _hash_to_u64(f"{base_seed}:rep:{repetition}")


@dataclass
class RNGManager:
    """Provides deterministic, named child streams from one base seed."""

    base_seed: int
    _streams: dict[str, random.Random] = field(default_factory=dict, init=False, repr=False)

    def child_seed(self, name: str) -> int:
        """
        Deterministically map a stream name to a child seed.
        """
        if not name:
            raise ValueError("stream name must be non-empty")
        return _hash_to_u64(f"{self.base_seed}:{name}")

    def stream(self, name: str) -> random.Random:
        """
        Returns a persistent RNG stream for the given subsystem name.
        """
        if name not in self._streams:
            self._streams[name] = random.Random(self.child_seed(name))
        return self._streams[name]

    def reset(self) -> None:
        """
        Reset all child stream state (same names will replay identically).
        """
        self._streams.clear()
