from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.metrics import compute_exe, compute_gcr, compute_ru, compute_sr, compute_tcr


class TestMetrics(unittest.TestCase):
    def test_metric_formulas(self):
        self.assertAlmostEqual(compute_exe(5, 5), 1.0)
        self.assertAlmostEqual(compute_ru(4, 8), 0.5)
        self.assertAlmostEqual(compute_gcr(3, 4), 0.75)
        self.assertAlmostEqual(compute_tcr(2, 4), 0.5)
        self.assertAlmostEqual(compute_sr(True, True), 1.0)
        self.assertAlmostEqual(compute_sr(True, False), 0.0)


if __name__ == "__main__":
    unittest.main()
