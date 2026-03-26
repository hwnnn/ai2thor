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

SLICEABLE_OBJECTS = ["Tomato", "Lettuce", "Potato", "Apple", "Bread"]
STORAGE_OBJECTS = ["Fridge", "Cabinet", "CounterTop"]
HEATABLE_OBJECTS = ["Bread", "Potato", "Apple"]
CLEANABLE_OBJECTS = ["Plate", "Bowl", "Cup", "Mug"]
REQUIRED_PARAMETERS = {
    "navigate": ("target_object",),
    "slice_and_store": ("source_object", "target_object"),
    "toggle_light": ("action",),
    "heat_object": ("object",),
    "clean_object": ("object",),
}
SUPPORTED_TASK_TYPES = set(FALLBACK_TASK_SKILL_MAP)


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
        payload = self._normalize_payload(payload, user_command)
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

    def _normalize_payload(self, payload: Dict[str, Any], user_command: str) -> Dict[str, Any]:
        normalized = [
            self._normalize_subtask(item, user_command)
            for item in payload.get("subtasks", [])
        ]
        normalized = self._prune_redundant_navigate_subtasks(normalized)

        if self._should_fallback_to_heuristic(normalized, user_command):
            return self._heuristic_decompose(user_command)

        return {"subtasks": normalized}

    def _should_fallback_to_heuristic(self, subtasks: List[Dict[str, Any]], user_command: str) -> bool:
        if not subtasks:
            return True

        task_types = [str(item.get("task_type", "")) for item in subtasks]
        if any(task_type not in SUPPORTED_TASK_TYPES for task_type in task_types):
            return True

        if self._has_unresolved_required_parameters(subtasks):
            return True

        expected_task_types = self._expected_task_types(user_command)
        actual_task_types = set(task_types)
        if not set(expected_task_types).issubset(actual_task_types):
            return True

        return False

    def _expected_task_types(self, user_command: str) -> List[str]:
        command = user_command.lower()
        expected: List[str] = []

        if any(token in user_command for token in ["썰", "자르", "슬라이스"]) or "slice" in command:
            expected.append("slice_and_store")
        if "불" in user_command or "light" in command or "스위치" in user_command:
            expected.append("toggle_light")
        if "데우" in user_command or "heat" in command:
            expected.append("heat_object")
        if "씻" in user_command or "clean" in command:
            expected.append("clean_object")

        return expected or ["navigate"]

    def _normalize_subtask(self, item: Dict[str, Any], user_command: str) -> Dict[str, Any]:
        normalized = dict(item)
        task_type = str(normalized.get("task_type", ""))
        description = str(normalized.get("description", ""))
        code_draft = str(normalized.get("code_draft", ""))
        texts = [description, code_draft, user_command]
        parameters = dict(normalized.get("parameters") or {})

        normalized["required_skills"] = list(
            self.task_skill_map.get(task_type, normalized.get("required_skills") or [])
        )

        if task_type == "navigate":
            target = parameters.get("target_object") or self._infer_object_from_texts(texts)
            if target:
                parameters["target_object"] = target

        elif task_type == "slice_and_store":
            source = parameters.get("source_object") or self._infer_object_from_texts(texts, preferred=SLICEABLE_OBJECTS)
            target = parameters.get("target_object") or self._infer_object_from_texts(texts, preferred=STORAGE_OBJECTS)
            if source:
                parameters["source_object"] = source
            if target:
                parameters["target_object"] = target

        elif task_type == "toggle_light":
            action = parameters.get("action")
            if action not in {"켜기", "끄기"}:
                parameters["action"] = self._infer_toggle_action(texts)

        elif task_type == "heat_object":
            obj_type = parameters.get("object") or self._infer_object_from_texts(texts, preferred=HEATABLE_OBJECTS)
            if obj_type:
                parameters["object"] = obj_type

        elif task_type == "clean_object":
            obj_type = parameters.get("object") or self._infer_object_from_texts(texts, preferred=CLEANABLE_OBJECTS)
            if obj_type:
                parameters["object"] = obj_type

        normalized["parameters"] = {
            key: value for key, value in parameters.items() if value is not None and value != ""
        }
        return normalized

    def _infer_object_from_texts(self, texts: List[str], preferred: List[str] | None = None) -> str:
        preferred = preferred or []
        for text in texts:
            if not text:
                continue
            matched = self._find_object_in_command(text, preferred=preferred, default="")
            if matched:
                return matched
            inferred = infer_object_type_from_text(text, fallback="")
            if inferred and (not preferred or inferred in preferred):
                return inferred
        return ""

    def _infer_toggle_action(self, texts: List[str]) -> str:
        joined = " ".join(texts).lower()
        if "켜" in joined or " turn on " in f" {joined} " or " on " in f" {joined} ":
            return "켜기"
        return "끄기"

    def _prune_redundant_navigate_subtasks(self, subtasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        dependents: Dict[str, List[str]] = {}
        by_id = {item["subtask_id"]: item for item in subtasks}

        for item in subtasks:
            for dep in item.get("dependencies", []):
                dependents.setdefault(dep, []).append(item["subtask_id"])

        removable = set()
        for item in subtasks:
            if item.get("task_type") != "navigate":
                continue
            linked = dependents.get(item["subtask_id"], [])
            if len(linked) != 1:
                continue

            dependent = by_id.get(linked[0])
            target_object = (item.get("parameters") or {}).get("target_object")
            if dependent is None or not target_object:
                continue

            if not self._navigate_is_redundant(target_object, dependent):
                continue

            removable.add(item["subtask_id"])
            dependent["dependencies"] = [
                dep for dep in dependent.get("dependencies", []) if dep != item["subtask_id"]
            ]

        return [item for item in subtasks if item["subtask_id"] not in removable]

    def _navigate_is_redundant(self, target_object: str, dependent: Dict[str, Any]) -> bool:
        params = dict(dependent.get("parameters") or {})
        task_type = dependent.get("task_type")

        if task_type == "slice_and_store":
            return target_object == params.get("source_object")
        if task_type == "heat_object":
            return target_object == params.get("object")
        if task_type == "clean_object":
            return target_object == params.get("object")
        if task_type == "toggle_light":
            return target_object == "LightSwitch"
        return False

    def _has_unresolved_required_parameters(self, subtasks: List[Dict[str, Any]]) -> bool:
        for item in subtasks:
            required = REQUIRED_PARAMETERS.get(item.get("task_type"), ())
            parameters = dict(item.get("parameters") or {})
            if any(not parameters.get(name) for name in required):
                return True
        return False

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
