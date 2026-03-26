from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List


CATALOG_PATH = Path(__file__).resolve().parent / "ai2thor_world.yaml"


@lru_cache(maxsize=1)
def load_world_knowledge() -> Dict[str, Any]:
    """Load AI2-THOR world catalog from YAML(JSON-compatible) file."""
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def scene_names() -> List[str]:
    catalog = load_world_knowledge()
    return list(catalog.get("scenes", {}).get("all", []))


def object_types() -> List[str]:
    catalog = load_world_knowledge()
    return [row.get("objectType", "") for row in catalog.get("objects", []) if row.get("objectType")]


def interactions() -> List[Dict[str, Any]]:
    catalog = load_world_knowledge()
    return list(catalog.get("interactions", []))


def interaction_to_skill_map() -> Dict[str, List[str]]:
    catalog = load_world_knowledge()
    table = catalog.get("interaction_to_skill", {})
    out: Dict[str, List[str]] = {}
    for action, skills in table.items():
        if isinstance(skills, list):
            out[action] = [str(skill) for skill in skills]
    return out


def task_type_to_skills_map() -> Dict[str, List[str]]:
    catalog = load_world_knowledge()
    table = catalog.get("task_type_to_skills", {})
    out: Dict[str, List[str]] = {}
    for task_type, skills in table.items():
        if isinstance(skills, list):
            out[task_type] = [str(skill) for skill in skills]
    return out


def alias_to_object_type() -> Dict[str, str]:
    """Lower-cased alias/objectType lookup table for heuristic decomposition."""
    lookup: Dict[str, str] = {}
    for row in load_world_knowledge().get("objects", []):
        obj_type = row.get("objectType")
        if not obj_type:
            continue
        lookup[obj_type.lower()] = obj_type
        for alias in row.get("aliases", []):
            lookup[str(alias).lower()] = obj_type
    return lookup


def format_scene_catalog() -> str:
    catalog = load_world_knowledge().get("scenes", {})
    lines = []
    for key in ["kitchen", "living_room", "bedroom", "bathroom"]:
        values = catalog.get(key, [])
        if values:
            lines.append(f"- {key}: {', '.join(values)}")
    return "\n".join(lines)


def format_object_catalog(max_count: int | None = 400) -> str:
    items = object_types()
    if max_count is not None:
        items = items[:max_count]
    return ", ".join(items)


def format_interaction_catalog() -> str:
    lines = []
    for row in interactions():
        action = row.get("action", "")
        kind = row.get("kind", "")
        skills = row.get("required_skills", [])
        if action:
            lines.append(f"- {action} ({kind}) -> skills={skills}")
    return "\n".join(lines)


def infer_object_type_from_text(text: str, fallback: str = "") -> str:
    lowered = text.lower()
    for alias, obj_type in alias_to_object_type().items():
        if alias and alias in lowered:
            return obj_type
    return fallback
