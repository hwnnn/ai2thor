#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_scene_names() -> list[str]:
    scenes = [f"FloorPlan{i}" for i in range(1, 31)]
    scenes += [f"FloorPlan{i}" for i in range(201, 231)]
    scenes += [f"FloorPlan{i}" for i in range(301, 331)]
    scenes += [f"FloorPlan{i}" for i in range(401, 431)]
    return scenes


def load_catalog(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_catalog(path: Path, catalog: dict) -> None:
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


def discover_objects(scenes: list[str], limit_scenes: int | None = None) -> set[str]:
    try:
        from ai2thor.controller import Controller
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("ai2thor is not installed in this environment") from exc

    selected = scenes[:limit_scenes] if limit_scenes else scenes
    object_types: set[str] = set()

    controller = Controller(scene=selected[0], width=300, height=300, quality="Very Low", renderDepthImage=False)
    try:
        for scene in selected:
            controller.reset(scene)
            for obj in controller.last_event.metadata.get("objects", []):
                obj_type = obj.get("objectType")
                if obj_type:
                    object_types.add(obj_type)
    finally:
        controller.stop()

    return object_types


def merge_objects(catalog: dict, object_types: set[str]) -> int:
    existing = {row.get("objectType") for row in catalog.get("objects", [])}
    added = 0
    for obj_type in sorted(object_types):
        if obj_type not in existing:
            catalog.setdefault("objects", []).append({"objectType": obj_type, "aliases": []})
            added += 1
    catalog["objects"] = sorted(catalog.get("objects", []), key=lambda row: row.get("objectType", ""))
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Update AI2-THOR world catalog from runtime scenes")
    parser.add_argument(
        "--catalog",
        default="src/smart_llm/knowledge/ai2thor_world.yaml",
        help="Path to catalog yaml(json-compatible) file",
    )
    parser.add_argument("--limit-scenes", type=int, default=None)
    args = parser.parse_args()

    catalog_path = Path(args.catalog)
    catalog = load_catalog(catalog_path)

    scenes = build_scene_names()
    discovered = discover_objects(scenes, limit_scenes=args.limit_scenes)
    added = merge_objects(catalog, discovered)
    save_catalog(catalog_path, catalog)

    print(f"Discovered objects: {len(discovered)}")
    print(f"Added new object types: {added}")
    print(f"Updated catalog: {catalog_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
