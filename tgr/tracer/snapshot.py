"""Local variable snapshotting for trace records."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

MAX_REPR = 80
MAX_ITEMS = 8


def snapshot_locals(values: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded, JSON-friendly representation of frame locals."""

    return {name: snapshot_value(value) for name, value in sorted(values.items())}


def snapshot_value(value: Any) -> Any:
    """Project a Python value into a compact trace representation."""

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, tuple):
        return _sequence("tuple", value)
    if isinstance(value, list):
        return _sequence("list", value)
    if isinstance(value, set | frozenset):
        return _sequence(type(value).__name__, sorted(value, key=repr))
    if isinstance(value, dict):
        return _mapping(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {"type": type(value).__name__, "fields": snapshot_value(asdict(value))}
    return _fingerprint(value)


def _sequence(kind: str, value: Any) -> dict[str, Any]:
    items = list(value)
    visible = items[:MAX_ITEMS]
    return {
        "type": kind,
        "len": len(items),
        "items": [snapshot_value(item) for item in visible],
        "truncated": len(items) > len(visible),
    }


def _mapping(value: dict[Any, Any]) -> dict[str, Any]:
    items = list(value.items())[:MAX_ITEMS]
    return {
        "type": "dict",
        "len": len(value),
        "items": [[snapshot_value(key), snapshot_value(val)] for key, val in items],
        "truncated": len(value) > len(items),
    }


def _fingerprint(value: Any) -> dict[str, Any]:
    text = repr(value)
    if len(text) > MAX_REPR:
        text = f"{text[:MAX_REPR - 3]}..."
    length = _safe_len(value)
    data: dict[str, Any] = {"type": type(value).__name__, "repr": text, "id": id(value)}
    if length is not None:
        data["len"] = length
    return data


def _safe_len(value: Any) -> int | None:
    try:
        return len(value)
    except TypeError:
        return None
