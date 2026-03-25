from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from smart_llm.models import RobotSpec, SkillSpec


@dataclass
class RuntimeConfig:
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    profile: str = "dev"
    dry_run: bool = True
    seed: int = 7
    max_agents: int = 3
    run_count: int = 1
    record_overhead_video: bool = False
    record_agent_video: bool = False
    record_dir: str = "output_videos"
    observer_fov: float = 35.0
    observer_height_padding: float = 0.0


def default_skills() -> List[SkillSpec]:
    return [
        SkillSpec(name="navigate", capabilities=["move", "rotate"]),
        SkillSpec(name="slice", capabilities=["slice_object"]),
        SkillSpec(name="pickup", capabilities=["pickup_object"]),
        SkillSpec(name="place", capabilities=["put_object"]),
        SkillSpec(name="open_close", capabilities=["open_object", "close_object"]),
        SkillSpec(name="toggle", capabilities=["toggle_object"]),
    ]


def default_robots(max_agents: int = 3) -> List[RobotSpec]:
    base = ["navigate", "pickup", "place", "toggle", "open_close", "slice"]
    robots = []
    for idx in range(max_agents):
        robots.append(RobotSpec(robot_id=f"agent{idx}", skills=list(base)))
    return robots
