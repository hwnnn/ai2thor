from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Sequence

from smart_llm.models import (
    AllocationEntry,
    ExecutableTask,
    RobotSpec,
    Stage1Output,
    Stage2Output,
    Stage3Output,
)
from smart_llm.schemas import SchemaValidator, stage3_to_dict


class TaskAllocator:
    def __init__(self, validator: SchemaValidator):
        self.validator = validator

    def run(
        self,
        stage1_output: Stage1Output,
        stage2_output: Stage2Output,
        robots: Sequence[RobotSpec],
    ) -> Stage3Output:
        subtasks_by_id = {s.subtask_id: s for s in stage1_output.subtasks}
        coalition_by_id = {c.subtask_id: c for c in stage2_output.coalitions}
        levels = self._dependency_levels(stage1_output)

        allocations: List[AllocationEntry] = []
        executable_plan: List[ExecutableTask] = []
        group_robot_usage = defaultdict(lambda: defaultdict(int))
        overall_robot_usage = defaultdict(int)

        non_parallel_offset = max(levels.values(), default=0) + 1
        serial_bucket = 0

        for subtask in stage1_output.subtasks:
            if subtask.parallelizable:
                thread_group = levels.get(subtask.subtask_id, 0)
            else:
                thread_group = non_parallel_offset + serial_bucket
                serial_bucket += 1

            coalition = coalition_by_id.get(subtask.subtask_id)
            team = (
                self._select_team(
                    coalition.candidate_teams,
                    thread_group=thread_group,
                    group_robot_usage=group_robot_usage,
                    overall_robot_usage=overall_robot_usage,
                )
                if coalition and coalition.candidate_teams
                else [robots[0].robot_id]
            )

            for robot_id in team:
                group_robot_usage[thread_group][robot_id] += 1
                overall_robot_usage[robot_id] += 1

            allocation = AllocationEntry(
                subtask_id=subtask.subtask_id,
                assigned_robots=team,
                thread_group=thread_group,
                dependencies=list(subtask.dependencies),
            )
            allocations.append(allocation)

            executable_plan.append(
                ExecutableTask(
                    subtask_id=subtask.subtask_id,
                    task_type=subtask.task_type,
                    parameters=dict(subtask.parameters),
                    assigned_robots=team,
                    thread_group=thread_group,
                    dependencies=list(subtask.dependencies),
                )
            )

        barriers = self._build_barriers(levels, subtasks_by_id)

        result = Stage3Output(
            allocations=allocations,
            barriers=barriers,
            executable_plan=executable_plan,
        )
        self.validator.validate_stage3(stage3_to_dict(result))
        return result

    def _select_team(
        self,
        candidate_teams: Sequence[Sequence[str]],
        thread_group: int,
        group_robot_usage: Dict[int, Dict[str, int]],
        overall_robot_usage: Dict[str, int],
    ) -> List[str]:
        def team_score(index_and_team):
            index, team = index_and_team
            overlap = sum(1 for robot_id in team if group_robot_usage[thread_group].get(robot_id, 0) > 0)
            max_group_load = max((group_robot_usage[thread_group].get(robot_id, 0) for robot_id in team), default=0)
            total_load = sum(overall_robot_usage.get(robot_id, 0) for robot_id in team)
            return (overlap, max_group_load, total_load, len(team), index)

        best_index, best_team = min(enumerate(candidate_teams), key=team_score)
        _ = best_index
        return list(best_team)

    def _dependency_levels(self, stage1_output: Stage1Output) -> Dict[str, int]:
        indegree = {}
        graph = defaultdict(list)
        level = {}

        for subtask in stage1_output.subtasks:
            indegree[subtask.subtask_id] = len(subtask.dependencies)
            level[subtask.subtask_id] = 0
            for dep in subtask.dependencies:
                graph[dep].append(subtask.subtask_id)

        queue = deque([sid for sid, deg in indegree.items() if deg == 0])

        while queue:
            node = queue.popleft()
            for nxt in graph[node]:
                indegree[nxt] -= 1
                level[nxt] = max(level[nxt], level[node] + 1)
                if indegree[nxt] == 0:
                    queue.append(nxt)

        unresolved = [sid for sid, deg in indegree.items() if deg > 0]
        if unresolved:
            raise ValueError(f"Cycle detected in dependencies: {unresolved}")

        return level

    def _build_barriers(self, levels: Dict[str, int], subtasks: Dict[str, object]) -> List[List[str]]:
        grouped = defaultdict(list)
        for sid, lv in levels.items():
            grouped[lv].append(sid)

        barriers: List[List[str]] = []
        for lv in sorted(grouped.keys()):
            current = [sid for sid in grouped[lv] if sid in subtasks]
            if current:
                barriers.append(sorted(current))
        return barriers
