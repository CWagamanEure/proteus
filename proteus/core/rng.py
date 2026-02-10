"""Deterministic RNG stream manager."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass


@dataclass
class RNGManager:
    """Provides deterministic, named child streams from one base seed."""

    base_seed: int

    def stream(self, name: str) -> random.Random:
        digest = hashlib.sha256(f"{self.base_seed}:{name}".encode("ascii")).digest()
        child_seed = int.from_bytes(digest[:8], "big", signed=False)
        return random.Random(child_seed)
