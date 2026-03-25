from __future__ import annotations

from typing import Any, Dict

from .json_schemas import (
    ROBOT_SKILL_SCHEMA,
    ENVIRONMENT_OBJECT_SCHEMA,
    STAGE1_SCHEMA,
    STAGE2_SCHEMA,
    STAGE3_SCHEMA,
)


class SchemaValidationError(ValueError):
    pass


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def _validate(value: Any, schema: Dict[str, Any], path: str = "$") -> None:
    expected_type = schema.get("type")
    if expected_type and not _type_ok(value, expected_type):
        raise SchemaValidationError(f"{path}: expected {expected_type}, got {type(value).__name__}")

    required = schema.get("required", [])
    if required:
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{path}: required keys only valid for object")
        for key in required:
            if key not in value:
                raise SchemaValidationError(f"{path}: missing required key '{key}'")

    min_length = schema.get("minLength")
    if min_length is not None:
        if not isinstance(value, str) or len(value) < min_length:
            raise SchemaValidationError(f"{path}: string shorter than minLength={min_length}")

    minimum = schema.get("minimum")
    if minimum is not None:
        if not isinstance(value, (int, float)) or value < minimum:
            raise SchemaValidationError(f"{path}: value below minimum={minimum}")

    min_items = schema.get("minItems")
    if min_items is not None:
        if not isinstance(value, list) or len(value) < min_items:
            raise SchemaValidationError(f"{path}: list smaller than minItems={min_items}")

    properties = schema.get("properties", {})
    if properties and isinstance(value, dict):
        for key, prop_schema in properties.items():
            if key in value:
                _validate(value[key], prop_schema, f"{path}.{key}")

    items_schema = schema.get("items")
    if items_schema and isinstance(value, list):
        for idx, item in enumerate(value):
            _validate(item, items_schema, f"{path}[{idx}]")


class SchemaValidator:
    def validate_robot(self, payload: Dict[str, Any]) -> None:
        _validate(payload, ROBOT_SKILL_SCHEMA)

    def validate_environment_object(self, payload: Dict[str, Any]) -> None:
        _validate(payload, ENVIRONMENT_OBJECT_SCHEMA)

    def validate_stage1(self, payload: Dict[str, Any]) -> None:
        _validate(payload, STAGE1_SCHEMA)

    def validate_stage2(self, payload: Dict[str, Any]) -> None:
        _validate(payload, STAGE2_SCHEMA)

    def validate_stage3(self, payload: Dict[str, Any]) -> None:
        _validate(payload, STAGE3_SCHEMA)
