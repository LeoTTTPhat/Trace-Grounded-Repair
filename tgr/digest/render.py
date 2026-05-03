"""Rendering helpers for digest comments."""

from __future__ import annotations

from typing import Any


def render_value(value: Any) -> str:
    if isinstance(value, dict) and "type" in value:
        kind = value["type"]
        if kind in {"list", "tuple", "set", "frozenset"}:
            open_bracket, close_bracket = ("(", ")") if kind == "tuple" else ("[", "]")
            items = ", ".join(render_value(item) for item in value.get("items", []))
            if value.get("truncated"):
                items = f"{items}, ..." if items else "..."
            return f"{open_bracket}{items}{close_bracket}"
        if kind == "dict":
            items = ", ".join(
                f"{render_value(key)}: {render_value(val)}" for key, val in value.get("items", [])
            )
            if value.get("truncated"):
                items = f"{items}, ..." if items else "..."
            return f"{{{items}}}"
        return f"<{kind} {value.get('repr', '')}>"
    return repr(value)


def compact_timeline(values: list[Any], limit: int = 5) -> str:
    if not values:
        return ""
    rendered = [render_value(value) for value in values]
    deduped: list[str] = []
    for item in rendered:
        if not deduped or deduped[-1] != item:
            deduped.append(item)
    if len(deduped) <= limit:
        return " -> ".join(deduped)
    middle = deduped[len(deduped) // 2]
    return f"{deduped[0]} -> {deduped[1]} -> ... -> {middle} -> {deduped[-1]} (n={len(deduped)})"
