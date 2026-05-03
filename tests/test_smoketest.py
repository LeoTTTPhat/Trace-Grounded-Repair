from __future__ import annotations

from pathlib import Path
import unittest

from tgr.harness import smoketest


class SmokeTest(unittest.TestCase):
    def test_smoketest_writes_run_artifacts(self) -> None:
        result = smoketest.run()

        self.assertFalse(result["passed"])
        self.assertGreater(result["events"], 0)
        run_dir = Path(smoketest.RUN_DIR)
        self.assertTrue((run_dir / "config.json").exists())
        self.assertTrue((run_dir / "trace.json").exists())
        self.assertTrue((run_dir / "digest.txt").exists())
        self.assertTrue((run_dir / "result.json").exists())
        self.assertIn("#@", (run_dir / "digest.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
