from __future__ import annotations

import os
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.llm.adapters import OpenAIAdapter, build_adapter


class TestLLMAdapters(unittest.TestCase):
    def test_build_openai_adapter_from_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            adapter = build_adapter("openai", "gpt-4.1-mini")
        self.assertIsInstance(adapter, OpenAIAdapter)
        self.assertEqual(adapter.model_name, "gpt-4.1-mini")

    def test_openai_adapter_requires_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                OpenAIAdapter(model_name="gpt-4.1-mini")


if __name__ == "__main__":
    unittest.main()
