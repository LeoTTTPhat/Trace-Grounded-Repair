"""Small metric helpers shared by experiment reports."""

from __future__ import annotations


def resolution_rate(results: list[bool]) -> float:
    if not results:
        return 0.0
    return sum(1 for result in results if result) / len(results)
