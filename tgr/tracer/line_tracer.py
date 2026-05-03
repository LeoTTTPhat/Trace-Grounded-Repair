"""Small `sys.settrace` wrapper for target-file line traces."""

from __future__ import annotations

import sys
from pathlib import Path
from types import FrameType
from typing import Any, Callable

from tgr.tracer.records import TraceEvent, TraceRecord
from tgr.tracer.snapshot import snapshot_locals, snapshot_value


class LineTracer:
    """Capture call, line, and return events for frames under target paths."""

    def __init__(self, target_paths: list[str | Path], max_events: int = 10_000):
        self.target_paths = {str(Path(path).resolve()) for path in target_paths}
        self.max_events = max_events
        self.record = TraceRecord()

    def trace_callable(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> TraceRecord:
        """Run `func` under tracing and return a `TraceRecord`."""

        self.record = TraceRecord()
        previous = sys.gettrace()
        sys.settrace(self._trace)
        try:
            self.record.result = snapshot_value(func(*args, **kwargs))
        except BaseException as exc:
            self.record.exception = f"{type(exc).__name__}: {exc}"
        finally:
            sys.settrace(previous)
        return self.record

    def _trace(self, frame: FrameType, event: str, arg: Any) -> Callable[..., Any] | None:
        if event not in {"call", "line", "return"}:
            return self._trace
        if not self._in_target(frame):
            return self._trace
        if len(self.record.events) >= self.max_events:
            return None

        locals_snapshot = snapshot_locals(frame.f_locals)
        if event == "return":
            locals_snapshot["return"] = snapshot_value(arg)

        self.record.add(
            TraceEvent(
                event=event,
                file=str(Path(frame.f_code.co_filename).resolve()),
                line=frame.f_lineno,
                function=frame.f_code.co_name,
                locals=locals_snapshot,
            )
        )
        return self._trace

    def _in_target(self, frame: FrameType) -> bool:
        return str(Path(frame.f_code.co_filename).resolve()) in self.target_paths
