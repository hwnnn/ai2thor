from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, Generator, List, Optional, Sequence, Set, Tuple

from smart_llm.models import ExecutableTask, Stage4Output, TaskExecutionResult

from .actions import execute_action


@dataclass
class ExecutionPolicy:
    max_retry: int = 1
    local_replan_enabled: bool = True
    global_replan_enabled: bool = True


@dataclass(frozen=True)
class ExecutionStep:
    name: str
    required_skills: Tuple[str, ...]


class InterleavingExecutor:
    def __init__(
        self,
        env_adapter,
        robot_skills: Optional[Dict[str, Set[str]]] = None,
        policy: Optional[ExecutionPolicy] = None,
    ):
        self.env = env_adapter
        self.robot_skills = robot_skills or {}
        self.policy = policy or ExecutionPolicy()

    def execute(
        self,
        plan: Sequence[ExecutableTask],
        global_replan_callback: Optional[Callable[[ExecutableTask, Set[str]], Optional[ExecutableTask]]] = None,
    ) -> Stage4Output:
        grouped = defaultdict(list)
        for task in plan:
            grouped[task.thread_group].append(task)

        completed: Set[str] = set()
        logs: List[str] = []
        results: List[TaskExecutionResult] = []
        total_transitions = 0

        for group_id in sorted(grouped.keys()):
            pending = {
                task.subtask_id: {
                    "task": task,
                    "gen": self._task_generator(task),
                    "attempts": 1,
                    "local_replanned": False,
                    "global_replanned": False,
                    "last_action_success": True,
                    "last_message": "",
                    "transitions": 0,
                }
                for task in grouped[group_id]
            }

            while pending:
                progressed = False

                for subtask_id in list(pending.keys()):
                    state = pending[subtask_id]
                    task = state["task"]

                    if not set(task.dependencies).issubset(completed):
                        continue

                    progressed = True
                    try:
                        action_result = next(state["gen"])
                        state["last_action_success"] = action_result.success
                        state["last_message"] = action_result.message
                        state["transitions"] += action_result.transitions
                        total_transitions += action_result.transitions
                        logs.append(f"[{task.subtask_id}] {action_result.status}: {action_result.message}")
                    except StopIteration:
                        if state["last_action_success"]:
                            completed.add(task.subtask_id)
                            results.append(
                                TaskExecutionResult(
                                    subtask_id=task.subtask_id,
                                    success=True,
                                    attempts=state["attempts"],
                                    message=state["last_message"] or "completed",
                                    transitions=state["transitions"],
                                )
                            )
                            del pending[subtask_id]
                            continue

                        can_retry = state["attempts"] <= self.policy.max_retry
                        if can_retry:
                            state["attempts"] += 1
                            state["gen"] = self._task_generator(task)
                            logs.append(f"[{task.subtask_id}] retry attempt {state['attempts']}")
                            continue

                        if self.policy.local_replan_enabled and not state["local_replanned"]:
                            replanned = self._local_replan(task)
                            state["task"] = replanned
                            state["gen"] = self._task_generator(replanned)
                            state["local_replanned"] = True
                            state["attempts"] += 1
                            logs.append(f"[{task.subtask_id}] local replan applied")
                            continue

                        if (
                            self.policy.global_replan_enabled
                            and global_replan_callback is not None
                            and not state["global_replanned"]
                        ):
                            new_task = global_replan_callback(task, completed)
                            state["global_replanned"] = True
                            if new_task is not None:
                                state["task"] = new_task
                                state["gen"] = self._task_generator(new_task)
                                state["attempts"] += 1
                                logs.append(f"[{task.subtask_id}] global replan applied")
                                continue

                        # Fail terminally.
                        results.append(
                            TaskExecutionResult(
                                subtask_id=task.subtask_id,
                                success=False,
                                attempts=state["attempts"],
                                message=state["last_message"] or "failed",
                                transitions=state["transitions"],
                            )
                        )
                        del pending[subtask_id]

                if not progressed:
                    # No runnable tasks left but pending remains: broken dependency.
                    for subtask_id, state in pending.items():
                        results.append(
                            TaskExecutionResult(
                                subtask_id=subtask_id,
                                success=False,
                                attempts=state["attempts"],
                                message="dependency deadlock",
                                transitions=state["transitions"],
                            )
                        )
                    pending.clear()

        success = all(r.success for r in results) and len(results) == len(plan)
        return Stage4Output(
            results=results,
            success=success,
            total_transitions=total_transitions,
            logs=logs,
        )

    def _task_generator(self, task: ExecutableTask) -> Generator:
        step_usage = defaultdict(int)

        for step in self._execution_steps(task.task_type):
            selected_robot = self._select_robot_for_step(task.assigned_robots, step.required_skills, step_usage)
            if selected_robot is None:
                yield execute_action(
                    lambda: False,
                    f"{task.subtask_id}:{step.name}:no_robot_for_{'+'.join(step.required_skills) or 'task'}",
                )
                return

            step_usage[selected_robot] += 1
            agent_id = self._parse_agent_id(selected_robot)

            if not self.env.check_precondition(task.task_type, task.parameters, agent_id=agent_id, step_name=step.name):
                yield execute_action(lambda: False, f"{task.subtask_id}:{step.name}:{selected_robot}:precondition")
                return

            if hasattr(self.env, "execute_step_iter"):
                for result in self.env.execute_step_iter(task.task_type, step.name, task.parameters, agent_id=agent_id):
                    prefixed_message = f"{task.subtask_id}:{step.name}:{selected_robot}:{result.message}"
                    yield type(result)(
                        success=result.success,
                        status=result.status,
                        message=prefixed_message,
                        error=result.error,
                        transitions=result.transitions,
                    )
                    if not result.success:
                        return
                continue

            yield execute_action(
                lambda: self.env.execute_step(task.task_type, step.name, task.parameters, agent_id=agent_id),
                f"{task.subtask_id}:{step.name}:{selected_robot}",
            )

    def _execution_steps(self, task_type: str) -> List[ExecutionStep]:
        if task_type == "slice_and_store":
            return [
                ExecutionStep(name="prepare_source", required_skills=("navigate", "slice")),
                ExecutionStep(name="transport_and_store", required_skills=("navigate", "pickup", "open_close", "place")),
            ]
        if task_type == "heat_object":
            return [
                ExecutionStep(name="load_microwave", required_skills=("navigate", "pickup", "open_close", "place")),
                ExecutionStep(name="activate_microwave", required_skills=("navigate", "toggle")),
            ]
        if task_type == "clean_object":
            return [
                ExecutionStep(name="place_in_sink", required_skills=("navigate", "pickup", "place")),
                ExecutionStep(name="toggle_faucet", required_skills=("navigate", "toggle")),
            ]
        if task_type == "toggle_light":
            return [ExecutionStep(name="navigate_and_toggle", required_skills=("navigate", "toggle"))]
        if task_type == "navigate":
            return [ExecutionStep(name="navigate", required_skills=("navigate",))]
        return [ExecutionStep(name="commit", required_skills=tuple())]

    def _select_robot_for_step(
        self,
        assigned_robots: Sequence[str],
        required_skills: Sequence[str],
        step_usage: Dict[str, int],
    ) -> Optional[str]:
        if not assigned_robots:
            return None

        if not required_skills or not self.robot_skills:
            return assigned_robots[0]

        eligible = [
            robot_id
            for robot_id in assigned_robots
            if set(required_skills).issubset(self.robot_skills.get(robot_id, set()))
        ]
        if not eligible:
            return None

        return min(eligible, key=lambda robot_id: (step_usage.get(robot_id, 0), assigned_robots.index(robot_id)))

    def _parse_agent_id(self, robot_id: str) -> int:
        digits = "".join(ch for ch in robot_id if ch.isdigit())
        return int(digits) if digits else 0

    def _local_replan(self, task: ExecutableTask) -> ExecutableTask:
        return ExecutableTask(
            subtask_id=task.subtask_id,
            task_type=task.task_type,
            parameters=dict(task.parameters),
            assigned_robots=list(task.assigned_robots),
            thread_group=task.thread_group,
            dependencies=list(task.dependencies),
        )
