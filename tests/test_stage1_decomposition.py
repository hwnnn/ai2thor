from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.schemas import SchemaValidator
from smart_llm.stages.stage1_decomposition import Stage1Decomposer


class StaticAdapter:
    allow_heuristic_fallback = False

    def __init__(self, payload):
        self.payload = payload
        self.last_response = None

    def generate_json(self, prompt: str):
        _ = prompt
        return self.payload


class TestStage1Decomposition(unittest.TestCase):
    def test_normalizes_parameters_and_prunes_redundant_navigation(self):
        adapter = StaticAdapter(
            {
                "subtasks": [
                    {
                        "subtask_id": "S1",
                        "task_type": "navigate",
                        "description": "Navigate to the tomato",
                        "required_skills": ["navigate"],
                        "dependencies": [],
                        "parallelizable": True,
                        "parameters": {},
                        "code_draft": "navigate(Tomato)",
                    },
                    {
                        "subtask_id": "S2",
                        "task_type": "slice_and_store",
                        "description": "Slice the tomato and prepare to store it",
                        "required_skills": ["navigate"],
                        "dependencies": ["S1"],
                        "parallelizable": True,
                        "parameters": {"source_object": "Tomato"},
                        "code_draft": "slice(Tomato); pickup(TomatoSliced); store()",
                    },
                    {
                        "subtask_id": "S3",
                        "task_type": "toggle_light",
                        "description": "Turn off the light",
                        "required_skills": ["navigate"],
                        "dependencies": [],
                        "parallelizable": True,
                        "parameters": {},
                        "code_draft": "navigate(LightSwitch); toggle(LightSwitch)",
                    },
                ]
            }
        )
        decomposer = Stage1Decomposer(adapter=adapter, validator=SchemaValidator())

        result = decomposer.run(
            user_command="토마토를 썰어서 냉장고에 넣고, 불을 꺼줘",
            skills=[],
            objects=[],
        )

        self.assertEqual([subtask.subtask_id for subtask in result.subtasks], ["S2", "S3"])
        self.assertEqual(result.subtasks[0].parameters, {"source_object": "Tomato", "target_object": "Fridge"})
        self.assertEqual(result.subtasks[0].dependencies, [])
        self.assertEqual(result.subtasks[1].parameters, {"action": "끄기"})

    def test_falls_back_to_macro_tasks_for_granular_heat_and_clean_plan(self):
        adapter = StaticAdapter(
            {
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
        )
        decomposer = Stage1Decomposer(adapter=adapter, validator=SchemaValidator())

        result = decomposer.run(
            user_command="빵을 전자레인지로 데우고, 접시를 씻어줘",
            skills=[],
            objects=[],
        )

        self.assertEqual([subtask.task_type for subtask in result.subtasks], ["heat_object", "clean_object"])
        self.assertEqual(result.subtasks[0].parameters, {"object": "Bread"})
        self.assertEqual(result.subtasks[1].parameters, {"object": "Plate"})
        self.assertTrue(all(subtask.parallelizable for subtask in result.subtasks))


if __name__ == "__main__":
    unittest.main()
