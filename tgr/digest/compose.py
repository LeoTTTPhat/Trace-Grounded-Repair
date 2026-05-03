"""Compose trace projections into a source-shaped digest."""

from __future__ import annotations

from collections import defaultdict

from tgr.digest.aliases import alias_comments
from tgr.digest.branches import branch_comments
from tgr.digest.values import value_comments
from tgr.tracer.records import TraceRecord


def compose(source: str, trace: TraceRecord) -> str:
    """Insert line-aligned `#@` comments above the source lines they describe."""

    comments: dict[int, list[str]] = defaultdict(list)
    for projection in (value_comments(trace), branch_comments(source, trace), alias_comments(trace)):
        for line, lines in projection.items():
            comments[line].extend(lines)

    output: list[str] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        indent = line[: len(line) - len(line.lstrip())]
        for comment in comments.get(line_number, []):
            output.append(f"{indent}{comment}")
        output.append(line)
    if source.endswith("\n"):
        return "\n".join(output) + "\n"
    return "\n".join(output)
