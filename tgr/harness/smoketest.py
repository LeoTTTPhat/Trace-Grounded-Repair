"""End-to-end smoke test for the Phase 0 trace digest pipeline."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from tgr.digest import compose
from tgr.harness.toy_bug import rolling_max
from tgr.tracer import LineTracer

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / "runs" / "smoketest"
INPUT = {"xs": [1, 5, 3, 2, 8], "k": 3}
EXPECTED = [5, 5, 8]


def run() -> dict[str, object]:
    source_path = Path(inspect.getsourcefile(rolling_max) or "").resolve()
    source = source_path.read_text(encoding="utf-8")
    tracer = LineTracer([source_path])
    trace = tracer.trace_callable(rolling_max, INPUT["xs"], INPUT["k"])
    digest = compose(source, trace)
    passed = trace.result == EXPECTED

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "config.json").write_text(
        json.dumps({"target": str(source_path), "input": INPUT, "expected": EXPECTED}, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUN_DIR / "trace.json").write_text(json.dumps(trace.to_dict(), indent=2) + "\n", encoding="utf-8")
    (RUN_DIR / "digest.txt").write_text(digest, encoding="utf-8")
    result = {
        "passed": passed,
        "observed": trace.result,
        "expected": EXPECTED,
        "events": len(trace.events),
        "digest": str(RUN_DIR / "digest.txt"),
    }
    (RUN_DIR / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    result = run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
