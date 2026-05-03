"""Local alias summary projection."""

from __future__ import annotations

from collections import defaultdict

from tgr.tracer.records import TraceRecord


def alias_comments(trace: TraceRecord) -> dict[int, list[str]]:
    """Summarize local names that point at the same mutable object id."""

    if not trace.events:
        return {}
    last = trace.events[-1]
    by_id: dict[int, list[str]] = defaultdict(list)
    for name, value in last.locals.items():
        if isinstance(value, dict) and "id" in value:
            by_id[value["id"]].append(name)
    aliases = [names for names in by_id.values() if len(names) > 1]
    if not aliases:
        return {}
    rendered = "; ".join(" is ".join(sorted(names)) for names in aliases)
    return {last.line: [f"#@ aliases at end: {rendered}"]}
