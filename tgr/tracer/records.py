"""Structured trace record types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TraceEvent:
    """One observed execution event."""

    event: str
    file: str
    line: int
    function: str
    locals: dict[str, Any]


@dataclass
class TraceRecord:
    """A compact, serializable trace for one failing run."""

    events: list[TraceEvent] = field(default_factory=list)
    result: Any = None
    exception: str | None = None

    def add(self, event: TraceEvent) -> None:
        self.events.append(event)

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [asdict(event) for event in self.events],
            "result": self.result,
            "exception": self.exception,
        }
