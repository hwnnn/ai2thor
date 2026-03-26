from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class SkillSpec:
    name: str
    constraints: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)


@dataclass
class RobotSpec:
    robot_id: str
    skills: List[str]
    constraints: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)


@dataclass
class EnvironmentObject:
    objectType: str
    state: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, float] = field(default_factory=dict)
    affordance: List[str] = field(default_factory=list)


@dataclass
class Subtask:
    subtask_id: str
    task_type: str
    description: str
    required_skills: List[str]
    dependencies: List[str] = field(default_factory=list)
    parallelizable: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    code_draft: str = ""


@dataclass
class Stage1Output:
    subtasks: List[Subtask]


@dataclass
class CoalitionPlan:
    subtask_id: str
    required_skills: List[str]
    single_robot_possible: bool
    min_team_size: int
    candidate_teams: List[List[str]]


@dataclass
class Stage2Output:
    coalitions: List[CoalitionPlan]
    coalition_policy_text: str


@dataclass
class AllocationEntry:
    subtask_id: str
    assigned_robots: List[str]
    thread_group: int
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ExecutableTask:
    subtask_id: str
    task_type: str
    parameters: Dict[str, Any]
    assigned_robots: List[str]
    thread_group: int
    dependencies: List[str]


@dataclass
class Stage3Output:
    allocations: List[AllocationEntry]
    barriers: List[List[str]]
    executable_plan: List[ExecutableTask]


@dataclass
class ActionResult:
    success: bool
    status: str
    message: str
    error: Optional[str] = None
    transitions: int = 0


@dataclass
class TaskExecutionResult:
    subtask_id: str
    success: bool
    attempts: int
    message: str
    transitions: int = 0


@dataclass
class Stage4Output:
    results: List[TaskExecutionResult]
    success: bool
    total_transitions: int
    logs: List[str] = field(default_factory=list)
