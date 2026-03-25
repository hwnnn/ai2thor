from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List

from smart_llm.models import (
    Stage1Output,
    Stage2Output,
    Stage3Output,
    Subtask,
    CoalitionPlan,
    AllocationEntry,
    ExecutableTask,
)


def stage1_to_dict(stage1: Stage1Output) -> Dict:
    return asdict(stage1)


def stage2_to_dict(stage2: Stage2Output) -> Dict:
    return asdict(stage2)


def stage3_to_dict(stage3: Stage3Output) -> Dict:
    return asdict(stage3)


def stage1_from_dict(data: Dict) -> Stage1Output:
    subtasks: List[Subtask] = [Subtask(**s) for s in data.get("subtasks", [])]
    return Stage1Output(subtasks=subtasks)


def stage2_from_dict(data: Dict) -> Stage2Output:
    coalitions: List[CoalitionPlan] = [CoalitionPlan(**c) for c in data.get("coalitions", [])]
    return Stage2Output(
        coalitions=coalitions,
        coalition_policy_text=data.get("coalition_policy_text", ""),
    )


def stage3_from_dict(data: Dict) -> Stage3Output:
    allocations: List[AllocationEntry] = [AllocationEntry(**a) for a in data.get("allocations", [])]
    executable_plan: List[ExecutableTask] = [ExecutableTask(**p) for p in data.get("executable_plan", [])]
    return Stage3Output(
        allocations=allocations,
        barriers=data.get("barriers", []),
        executable_plan=executable_plan,
    )
