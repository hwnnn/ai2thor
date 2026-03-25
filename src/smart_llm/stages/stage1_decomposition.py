from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from smart_llm.knowledge import (
    format_interaction_catalog,
    format_object_catalog,
    format_scene_catalog,
    infer_object_type_from_text,
    load_world_knowledge,
    task_type_to_skills_map,
)
from smart_llm.llm import BaseLLMAdapter
from smart_llm.llm.prompt_yaml import parse_simple_yaml
from smart_llm.models import EnvironmentObject, SkillSpec, Stage1Output, Subtask
from smart_llm.schemas import SchemaValidator, stage1_to_dict


FALLBACK_TASK_SKILL_MAP = {
    "slice_and_store": ["navigate", "slice", "pickup", "place", "open_close"],
    "toggle_light": ["navigate", "toggle"],
    "heat_object": ["navigate", "pickup", "open_close", "toggle", "place"],
    "clean_object": ["navigate", "pickup", "toggle", "place"],
    "navigate": ["navigate"],
}


class Stage1Decomposer:
    def __init__(self, adapter: BaseLLMAdapter, validator: SchemaValidator):
        self.adapter = adapter
        self.validator = validator

        prompt_path = Path(__file__).resolve().parent.parent / "llm" / "prompts" / "stage1_task_decomposition.yaml"
        self.prompt_spec = parse_simple_yaml(prompt_path.read_text(encoding="utf-8"))

        catalog = load_world_knowledge()
        self.objects_by_type: Dict[str, Dict[str, Any]] = {
            row.get("objectType", ""): row for row in catalog.get("objects", []) if row.get("objectType")
        }
        self.task_skill_map = {**FALLBACK_TASK_SKILL_MAP, **task_type_to_skills_map()}

    def run(
        self,
        user_command: str,
        skills: List[SkillSpec],
        objects: List[EnvironmentObject],
    ) -> Stage1Output:
        prompt = self._build_prompt(user_command=user_command, skills=skills, objects=objects)

        try:
            payload = self.adapter.generate_json(prompt)
        except Exception as exc:
            if not getattr(self.adapter, "allow_heuristic_fallback", False):
                raise RuntimeError(f"Stage 1 decomposition failed: {exc}") from exc
            payload = self._heuristic_decompose(user_command)

        self.validator.validate_stage1(payload)
        subtasks = [Subtask(**item) for item in payload["subtasks"]]
        return Stage1Output(subtasks=subtasks)

    def _build_prompt(self, user_command: str, skills: List[SkillSpec], objects: List[EnvironmentObject]) -> str:
        system = self.prompt_spec.get("system", "")
        rules = self.prompt_spec.get("rules", [])
        task_types = self.prompt_spec.get("task_types", [])
        output_schema_raw = self.prompt_spec.get("output_schema_json", "{}")
        output_schema = json.loads(output_schema_raw) if isinstance(output_schema_raw, str) else {}
        prompt_template = self.prompt_spec.get("prompt_template", "")

        rendered_template = prompt_template
        rendered_template = rendered_template.replace("{user_command}", user_command)
        rendered_template = rendered_template.replace("{scene_catalog}", format_scene_catalog())
        rendered_template = rendered_template.replace("{object_catalog}", format_object_catalog(max_count=600))
        rendered_template = rendered_template.replace("{interaction_catalog}", format_interaction_catalog())
        rendered_template = rendered_template.replace("{skills_json}", json.dumps([s.__dict__ for s in skills], ensure_ascii=False))
        rendered_template = rendered_template.replace("{objects_json}", json.dumps([o.__dict__ for o in objects[:80]], ensure_ascii=False))

        lines: List[str] = [system]
        if task_types:
            lines.append("Known task types:\n- " + "\n- ".join(task_types))
        if rules:
            lines.append("Rules:\n" + "\n".join(f"{idx + 1}. {rule}" for idx, rule in enumerate(rules)))

        lines.append("Output schema:\n" + json.dumps(output_schema, ensure_ascii=False, indent=2))
        lines.append(rendered_template)
        return "\n\n".join(lines).strip()

    def _heuristic_decompose(self, user_command: str) -> Dict[str, Any]:
        command = user_command.lower()
        subtasks = []
        sid = 1

        source_for_cut = self._find_object_in_command(
            user_command,
            preferred=["Tomato", "Lettuce", "Potato", "Apple", "Bread"],
            default="Tomato",
        )
        storage_target = self._find_object_in_command(
            user_command,
            preferred=["Fridge", "Cabinet", "CounterTop"],
            default="Fridge",
        )

        if any(token in user_command for token in ["썰", "자르", "슬라이스"]) or "slice" in command:
            subtasks.append(
                {
                    "subtask_id": f"S{sid}",
                    "task_type": "slice_and_store",
                    "description": f"{source_for_cut}를 썰어 {storage_target}에 넣기",
                    "required_skills": self.task_skill_map["slice_and_store"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"source_object": source_for_cut, "target_object": storage_target},
                    "code_draft": (
                        "navigate(source); slice(source); pickup(source_sliced); "
                        "navigate(target); open(target); place(target)"
                    ),
                }
            )
            sid += 1

        if "불" in user_command or "light" in command or "스위치" in user_command:
            action = "끄기"
            if "켜" in user_command or "on" in command:
                action = "켜기"
            elif "꺼" in user_command or "off" in command:
                action = "끄기"

            subtasks.append(
                {
                    "subtask_id": f"S{sid}",
                    "task_type": "toggle_light",
                    "description": f"불 {action}",
                    "required_skills": self.task_skill_map["toggle_light"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"action": action},
                    "code_draft": "navigate(LightSwitch); toggle(LightSwitch)",
                }
            )
            sid += 1

        if "데우" in user_command or "heat" in command:
            heat_obj = self._find_object_in_command(user_command, preferred=["Bread", "Potato", "Apple"], default="Bread")
            subtasks.append(
                {
                    "subtask_id": f"S{sid}",
                    "task_type": "heat_object",
                    "description": f"{heat_obj}를 전자레인지로 데우기",
                    "required_skills": self.task_skill_map["heat_object"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"object": heat_obj},
                    "code_draft": (
                        "navigate(obj); pickup(obj); navigate(Microwave); "
                        "open(Microwave); place(Microwave); toggle(Microwave)"
                    ),
                }
            )
            sid += 1

        if "씻" in user_command or "clean" in command:
            clean_obj = self._find_object_in_command(user_command, preferred=["Plate", "Bowl", "Cup", "Mug"], default="Plate")
            subtasks.append(
                {
                    "subtask_id": f"S{sid}",
                    "task_type": "clean_object",
                    "description": f"{clean_obj}를 싱크에서 세척",
                    "required_skills": self.task_skill_map["clean_object"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"object": clean_obj},
                    "code_draft": "navigate(obj); pickup(obj); navigate(SinkBasin); place(SinkBasin); toggle(Faucet)",
                }
            )
            sid += 1

        if not subtasks:
            navigate_target = self._find_object_in_command(
                user_command,
                preferred=["CounterTop", "Fridge", "SinkBasin", "Microwave"],
                default="CounterTop",
            )
            subtasks.append(
                {
                    "subtask_id": "S1",
                    "task_type": "navigate",
                    "description": f"{navigate_target}로 이동",
                    "required_skills": self.task_skill_map["navigate"],
                    "dependencies": [],
                    "parallelizable": True,
                    "parameters": {"target_object": navigate_target},
                    "code_draft": "navigate(target)",
                }
            )

        return {"subtasks": subtasks}

    def _find_object_in_command(self, user_command: str, preferred: List[str], default: str) -> str:
        lowered = user_command.lower()

        for obj_type in preferred:
            if obj_type.lower() in lowered:
                return obj_type
            aliases = self.objects_by_type.get(obj_type, {}).get("aliases", [])
            for alias in aliases:
                if str(alias).lower() in lowered:
                    return obj_type

        inferred = infer_object_type_from_text(user_command, fallback="")
        if inferred and (not preferred or inferred in preferred):
            return inferred

        return default


def stage1_to_payload(stage1_output: Stage1Output):
    return stage1_to_dict(stage1_output)
