from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.schemas import SchemaValidationError, SchemaValidator


class TestSchemaValidator(unittest.TestCase):
    def setUp(self):
        self.validator = SchemaValidator()

    def test_stage1_valid_payload(self):
        payload = {
            "subtasks": [
                {
                    "subtask_id": "S1",
                    "task_type": "navigate",
                    "description": "move",
                    "required_skills": ["navigate"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"target_object": "CounterTop"},
                    "code_draft": "navigate(target)",
                }
            ]
        }
        self.validator.validate_stage1(payload)

    def test_stage1_missing_required_field(self):
        payload = {
            "subtasks": [
                {
                    "subtask_id": "S1",
                    "task_type": "navigate",
                    "description": "move",
                    "required_skills": ["navigate"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {},
                }
            ]
        }

        with self.assertRaises(SchemaValidationError):
            self.validator.validate_stage1(payload)


if __name__ == "__main__":
    unittest.main()
