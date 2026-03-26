from __future__ import annotations

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smart_llm.execution.executor import InterleavingExecutor
from smart_llm.models import ActionResult, ExecutableTask


class RecordingEnv:
    def __init__(self):
        self.calls = []

    def check_precondition(self, task_type, parameters, agent_id=0, step_name=None):
        self.calls.append(("precondition", task_type, step_name, agent_id))
        return True

    def execute_step(self, task_type, step_name, parameters, agent_id=0):
        self.calls.append(("execute", task_type, step_name, agent_id))
        return True


class StepwiseEnv:
    def __init__(self):
        self.calls = []

    def check_precondition(self, task_type, parameters, agent_id=0, step_name=None):
        return True

    def execute_step_iter(self, task_type, step_name, parameters, agent_id=0):
        for tick in range(2):
            self.calls.append((agent_id, tick))
            yield ActionResult(
                success=True,
                status="progress",
                message=f"{task_type}:{step_name}:tick{tick}",
                transitions=1,
            )


class TestExecution(unittest.TestCase):
    def test_executor_uses_assigned_robot_skills_per_step(self):
        env = RecordingEnv()
        robot_skills = {
            "agent0": {"navigate", "pickup", "open_close", "place"},
            "agent1": {"navigate", "slice"},
        }
        executor = InterleavingExecutor(env_adapter=env, robot_skills=robot_skills)
        plan = [
            ExecutableTask(
                subtask_id="S1",
                task_type="slice_and_store",
                parameters={"source_object": "Tomato", "target_object": "Fridge"},
                assigned_robots=["agent0", "agent1"],
                thread_group=0,
                dependencies=[],
            )
        ]

        result = executor.execute(plan)

        self.assertTrue(result.success)
        execute_calls = [call for call in env.calls if call[0] == "execute"]
        self.assertEqual(execute_calls[0][2:], ("prepare_source", 1))
        self.assertEqual(execute_calls[1][2:], ("transport_and_store", 0))

    def test_executor_interleaves_primitive_actions_across_parallel_tasks(self):
        env = StepwiseEnv()
        executor = InterleavingExecutor(env_adapter=env, robot_skills={"agent0": {"navigate"}, "agent1": {"navigate"}})
        plan = [
            ExecutableTask(
                subtask_id="S1",
                task_type="navigate",
                parameters={"target_object": "CounterTop"},
                assigned_robots=["agent0"],
                thread_group=0,
                dependencies=[],
            ),
            ExecutableTask(
                subtask_id="S2",
                task_type="navigate",
                parameters={"target_object": "CounterTop"},
                assigned_robots=["agent1"],
                thread_group=0,
                dependencies=[],
            ),
        ]

        result = executor.execute(plan)

        self.assertTrue(result.success)
        self.assertEqual(env.calls, [(0, 0), (1, 0), (0, 1), (1, 1)])


if __name__ == "__main__":
    unittest.main()
