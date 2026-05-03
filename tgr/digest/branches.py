"""Branch ledger projection."""

from __future__ import annotations

import ast
from collections import defaultdict

from tgr.tracer.records import TraceRecord


class _BranchVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.lines: set[int] = set()

    def visit_If(self, node: ast.If) -> None:
        self.lines.add(node.lineno)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.lines.add(node.lineno)
        self.generic_visit(node)


def branch_comments(source: str, trace: TraceRecord) -> dict[int, list[str]]:
    """Render a simple executed-conditional ledger."""

    visitor = _BranchVisitor()
    visitor.visit(ast.parse(source))
    hits: dict[int, int] = defaultdict(int)
    for event in trace.events:
        if event.event == "line" and event.line in visitor.lines:
            hits[event.line] += 1

    comments: dict[int, list[str]] = defaultdict(list)
    for line in sorted(visitor.lines):
        if hits[line]:
            comments[line].append(f"#@ branch condition evaluated {hits[line]} time(s)")
    return comments
