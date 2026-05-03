"""Value timeline projection."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from tgr.digest.render import compact_timeline
from tgr.tracer.records import TraceRecord


def value_comments(trace: TraceRecord) -> dict[int, list[str]]:
    """Build line-keyed value timeline comments from trace events."""

    timelines: dict[int, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    for event in trace.events:
        if event.event != "line":
            continue
        for name, value in event.locals.items():
            if name.startswith("__"):
                continue
            timelines[event.line][name].append(value)

    comments: dict[int, list[str]] = defaultdict(list)
    for line, by_name in timelines.items():
        fragments: list[str] = []
        for name, values in sorted(by_name.items()):
            timeline = compact_timeline(values)
            if timeline:
                fragments.append(f"{name}: {timeline}")
        if fragments:
            comments[line].append("#@ values " + "; ".join(fragments))
    return comments
