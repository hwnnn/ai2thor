from __future__ import annotations

from itertools import combinations
from typing import Dict, Iterable, List, Sequence, Tuple

from smart_llm.knowledge import interaction_to_skill_map, task_type_to_skills_map
from smart_llm.models import CoalitionPlan, RobotSpec, Stage1Output, Stage2Output
from smart_llm.schemas import SchemaValidator, stage2_to_dict


DEFAULT_TASK_SKILLS = {
    "slice_and_store": ["navigate", "slice", "pickup", "place", "open_close"],
    "toggle_light": ["navigate", "toggle"],
    "heat_object": ["navigate", "pickup", "open_close", "toggle", "place"],
    "clean_object": ["navigate", "pickup", "toggle", "place"],
    "navigate": ["navigate"],
}

TASK_SKILLS_FROM_KNOWLEDGE = {**DEFAULT_TASK_SKILLS, **task_type_to_skills_map()}
INTERACTION_SKILLS_FROM_KNOWLEDGE = interaction_to_skill_map()


def _unique(items: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(items))


def extract_required_skills(task_type: str, explicit: Sequence[str], parameters: Dict | None = None) -> List[str]:
    if explicit:
        return _unique(list(explicit))

    skills = list(TASK_SKILLS_FROM_KNOWLEDGE.get(task_type, ["navigate"]))

    # Optional extension: when planner emits explicit actions, infer skills from interaction map.
    if isinstance(parameters, dict):
        actions = parameters.get("actions", [])
        if isinstance(actions, list):
            for action in actions:
                for skill in INTERACTION_SKILLS_FROM_KNOWLEDGE.get(str(action), []):
                    skills.append(skill)

    return _unique(skills)


def _covers(team: Iterable[RobotSpec], required_skills: Sequence[str]) -> bool:
    owned = set()
    for robot in team:
        owned.update(robot.skills)
    return all(skill in owned for skill in required_skills)


def _find_min_teams(robots: Sequence[RobotSpec], required_skills: Sequence[str], limit: int = 3) -> Tuple[int, List[List[str]]]:
    for size in range(1, len(robots) + 1):
        hits = []
        for combo in combinations(robots, size):
            if _covers(combo, required_skills):
                hits.append([robot.robot_id for robot in combo])
        if hits:
            return size, hits[:limit]
    return len(robots), []


class CoalitionFormer:
    def __init__(self, validator: SchemaValidator):
        self.validator = validator

    def run(self, stage1_output: Stage1Output, robots: Sequence[RobotSpec]) -> Stage2Output:
        coalitions: List[CoalitionPlan] = []

        for subtask in stage1_output.subtasks:
            required_skills = extract_required_skills(
                subtask.task_type,
                subtask.required_skills,
                parameters=subtask.parameters,
            )
            min_team_size, candidate_teams = _find_min_teams(robots, required_skills)

            single_robot_possible = any(len(team) == 1 for team in candidate_teams)
            coalition = CoalitionPlan(
                subtask_id=subtask.subtask_id,
                required_skills=required_skills,
                single_robot_possible=single_robot_possible,
                min_team_size=max(min_team_size, 1),
                candidate_teams=candidate_teams,
            )
            coalitions.append(coalition)

        policy_lines = []
        for coalition in coalitions:
            teams = ", ".join(str(team) for team in coalition.candidate_teams) if coalition.candidate_teams else "[]"
            policy_lines.append(
                f"{coalition.subtask_id}: skills={coalition.required_skills}, "
                f"single={coalition.single_robot_possible}, min_team={coalition.min_team_size}, teams={teams}"
            )

        result = Stage2Output(
            coalitions=coalitions,
            coalition_policy_text="\n".join(policy_lines),
        )

        payload = stage2_to_dict(result)
        self.validator.validate_stage2(payload)
        return result


def stage2_to_payload(stage2_output: Stage2Output) -> Dict:
    return stage2_to_dict(stage2_output)
