from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.config import RuntimeConfig
from smart_llm.pipeline import SMARTPipeline


class DummyAdapter:
    def __init__(self):
        self.model_name = "dummy"

    def generate_json(self, prompt: str):
        if "토마토" in prompt and "불" in prompt:
            return {
                "subtasks": [
                    {
                        "subtask_id": "S1",
                        "task_type": "slice_and_store",
                        "description": "토마토를 썰어서 냉장고에 넣기",
                        "required_skills": ["navigate", "slice", "pickup", "place", "open_close"],
                        "dependencies": [],
                        "parallelizable": True,
                        "parameters": {"source_object": "Tomato", "target_object": "Fridge"},
                        "code_draft": "...",
                    },
                    {
                        "subtask_id": "S2",
                        "task_type": "toggle_light",
                        "description": "불 끄기",
                        "required_skills": ["navigate", "toggle"],
                        "dependencies": [],
                        "parallelizable": True,
                        "parameters": {"action": "끄기"},
                        "code_draft": "...",
                    },
                ]
            }
        return {
            "subtasks": [
                {
                    "subtask_id": "S1",
                    "task_type": "toggle_light",
                    "description": "불 끄기",
                    "required_skills": ["navigate", "toggle"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"action": "끄기"},
                    "code_draft": "...",
                }
            ]
        }


class DummyGranularAdapter:
    def __init__(self):
        self.model_name = "dummy-granular"

    def generate_json(self, prompt: str):
        if "빵" in prompt and "접시" in prompt:
            return {
                "subtasks": [
                    {
                        "subtask_id": "S1",
                        "task_type": "navigate",
                        "description": "Navigate to the Bread location",
                        "required_skills": ["navigate"],
                        "dependencies": [],
                        "parallelizable": True,
                        "parameters": {"target_object": "Bread"},
                        "code_draft": "move_to_object('Bread')",
                    },
                    {
                        "subtask_id": "S2",
                        "task_type": "pickup",
                        "description": "Pickup the Bread",
                        "required_skills": ["pickup"],
                        "dependencies": ["S1"],
                        "parallelizable": False,
                        "parameters": {"objectType": "Bread"},
                        "code_draft": "pickup_object('Bread')",
                    },
                    {
                        "subtask_id": "S3",
                        "task_type": "clean_object",
                        "description": "Clean the Plate",
                        "required_skills": ["navigate", "pickup", "place", "toggle"],
                        "dependencies": [],
                        "parallelizable": False,
                        "parameters": {"objectType": "Plate"},
                        "code_draft": "clean_object('Plate')",
                    },
                ]
            }
        return DummyAdapter().generate_json(prompt)


class TestIntegrationPipeline(unittest.TestCase):
    def _pipeline(self):
        cfg = RuntimeConfig(provider="echo", model="echo", dry_run=True)
        pipeline = SMARTPipeline(cfg)
        pipeline.adapter = DummyAdapter()
        return pipeline

    def _granular_pipeline(self):
        cfg = RuntimeConfig(provider="echo", model="echo", dry_run=True)
        pipeline = SMARTPipeline(cfg)
        pipeline.adapter = DummyGranularAdapter()
        return pipeline

    def test_elemental_e2e(self):
        run = self._pipeline().run_once("불을 꺼줘")
        self.assertTrue(run.stage4["success"])
        self.assertGreaterEqual(len(run.stage1["subtasks"]), 1)
        self.assertEqual(run.artifacts["agent_count"], 1)

    def test_complex_e2e(self):
        run = self._pipeline().run_once("토마토를 썰어서 냉장고에 넣고, 불을 꺼줘")
        self.assertTrue(run.stage4["success"])
        self.assertGreaterEqual(len(run.stage1["subtasks"]), 2)
        groups = {a["thread_group"] for a in run.stage3["allocations"]}
        self.assertGreaterEqual(len(groups), 1)
        self.assertEqual(run.artifacts["agent_count"], 2)

    def test_granular_heat_and_clean_plan_is_normalized_to_two_agents(self):
        run = self._granular_pipeline().run_once("빵을 전자레인지로 데우고, 접시를 씻어줘")
        self.assertTrue(run.stage4["success"])
        self.assertEqual([subtask["task_type"] for subtask in run.stage1["subtasks"]], ["heat_object", "clean_object"])
        self.assertEqual(run.artifacts["agent_count"], 2)

    def test_goal_states_drive_metrics(self):
        run = self._pipeline().run_once(
            "불을 꺼줘",
            goal_states=[{"objectType": "LightSwitch", "state": {"isToggled": False}}],
        )
        self.assertEqual(run.metrics["GCR"], 1.0)
        self.assertEqual(run.metrics["SR"], 1.0)

        failed_goal_run = self._pipeline().run_once(
            "불을 꺼줘",
            goal_states=[{"objectType": "LightSwitch", "state": {"isToggled": True}}],
        )
        self.assertEqual(failed_goal_run.metrics["GCR"], 0.0)
        self.assertEqual(failed_goal_run.metrics["SR"], 0.0)


if __name__ == "__main__":
    unittest.main()
