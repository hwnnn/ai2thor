from __future__ import annotations

from typing import Optional, Sequence, Set

from smart_llm.execution.executor import ExecutionPolicy, InterleavingExecutor
from smart_llm.models import ExecutableTask, RobotSpec, Stage3Output, Stage4Output


class Stage4Executor:
    def __init__(self, env_adapter, robots: Sequence[RobotSpec], policy: Optional[ExecutionPolicy] = None):
        robot_skills = {robot.robot_id: set(robot.skills) for robot in robots}
        self.executor = InterleavingExecutor(
            env_adapter=env_adapter,
            robot_skills=robot_skills,
            policy=policy or ExecutionPolicy(global_replan_enabled=False),
        )

    def run(self, stage3_output: Stage3Output) -> Stage4Output:
        return self.executor.execute(stage3_output.executable_plan, global_replan_callback=None)
