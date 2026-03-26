from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.models import RobotSpec, Stage1Output, Subtask
from smart_llm.schemas import SchemaValidator
from smart_llm.stages import CoalitionFormer, TaskAllocator


class TestCoalitionAndAllocation(unittest.TestCase):
    def setUp(self):
        self.validator = SchemaValidator()
        self.robots = [
            RobotSpec(robot_id="agent0", skills=["navigate", "pickup"]),
            RobotSpec(robot_id="agent1", skills=["slice", "place", "open_close"]),
        ]

    def test_coalition_requires_team(self):
        stage1 = Stage1Output(
            subtasks=[
                Subtask(
                    subtask_id="S1",
                    task_type="slice_and_store",
                    description="slice and store",
                    required_skills=["navigate", "slice", "pickup", "place", "open_close"],
                    dependencies=[],
                    parallelizable=True,
                    parameters={"source_object": "Tomato", "target_object": "Fridge"},
                    code_draft="...",
                )
            ]
        )

        stage2 = CoalitionFormer(self.validator).run(stage1_output=stage1, robots=self.robots)
        coalition = stage2.coalitions[0]
        self.assertFalse(coalition.single_robot_possible)
        self.assertEqual(coalition.min_team_size, 2)
        self.assertIn(["agent0", "agent1"], coalition.candidate_teams)

    def test_allocation_respects_dependencies(self):
        stage1 = Stage1Output(
            subtasks=[
                Subtask(
                    subtask_id="S1",
                    task_type="navigate",
                    description="first",
                    required_skills=["navigate"],
                    dependencies=[],
                    parallelizable=True,
                    parameters={"target_object": "CounterTop"},
                    code_draft="...",
                ),
                Subtask(
                    subtask_id="S2",
                    task_type="navigate",
                    description="second",
                    required_skills=["navigate"],
                    dependencies=["S1"],
                    parallelizable=True,
                    parameters={"target_object": "Fridge"},
                    code_draft="...",
                ),
            ]
        )
        stage2 = CoalitionFormer(self.validator).run(stage1_output=stage1, robots=self.robots)
        stage3 = TaskAllocator(self.validator).run(stage1_output=stage1, stage2_output=stage2, robots=self.robots)

        alloc = {row.subtask_id: row for row in stage3.allocations}
        self.assertLess(alloc["S1"].thread_group, alloc["S2"].thread_group)
        self.assertEqual(stage3.barriers[0], ["S1"])

    def test_allocator_balances_parallel_tasks_across_robots(self):
        robots = [
            RobotSpec(robot_id="agent0", skills=["navigate"]),
            RobotSpec(robot_id="agent1", skills=["navigate"]),
        ]
        stage1 = Stage1Output(
            subtasks=[
                Subtask(
                    subtask_id="S1",
                    task_type="navigate",
                    description="first",
                    required_skills=["navigate"],
                    dependencies=[],
                    parallelizable=True,
                    parameters={"target_object": "CounterTop"},
                    code_draft="...",
                ),
                Subtask(
                    subtask_id="S2",
                    task_type="navigate",
                    description="second",
                    required_skills=["navigate"],
                    dependencies=[],
                    parallelizable=True,
                    parameters={"target_object": "Fridge"},
                    code_draft="...",
                ),
            ]
        )

        stage2 = CoalitionFormer(self.validator).run(stage1_output=stage1, robots=robots)
        stage3 = TaskAllocator(self.validator).run(stage1_output=stage1, stage2_output=stage2, robots=robots)

        assigned = {row.subtask_id: row.assigned_robots[0] for row in stage3.allocations}
        self.assertNotEqual(assigned["S1"], assigned["S2"])


if __name__ == "__main__":
    unittest.main()
