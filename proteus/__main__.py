"""Run basic package smoke check."""

from __future__ import annotations

from proteus.core.smoke import run_smoke_check

if __name__ == "__main__":
    print(run_smoke_check())
