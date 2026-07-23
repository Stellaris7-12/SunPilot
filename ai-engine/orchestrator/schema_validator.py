"""Lightweight JSON-schema validation for AgentCard runtime contracts."""

from __future__ import annotations

from typing import Any


class SchemaValidationError(ValueError):
    """Raised when an agent payload does not satisfy its AgentCard schema."""


def validate_agent_payload(
    payload: Any,
    schema: dict | None,
    *,
    agent_id: str,
    direction: str,
) -> None:
    """Validate one agent input or output payload.

    The project only needs a small JSON Schema subset for AgentCard contracts,
    so this avoids adding a runtime dependency just for schema checks.
    """
    if not schema:
        return
    label = f"{agent_id}.{direction}"
    errors: list[str] = []
    _validate(payload, schema, path="$", errors=errors)
    if errors:
        raise SchemaValidationError(f"{label} schema validation failed: {errors[0]}")


def _validate(value: Any, schema: dict, *, path: str, errors: list[str]) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        errors.append(f"{path} expected {expected_type}, got {_type_name(value)}")
        return

    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        errors.append(f"{path} expected one of {enum_values}, got {value!r}")
        return

    if isinstance(value, dict):
        _validate_object(value, schema, path=path, errors=errors)
    elif isinstance(value, list):
        _validate_array(value, schema, path=path, errors=errors)


def _validate_object(value: dict, schema: dict, *, path: str, errors: list[str]) -> None:
    required = schema.get("required", [])
    for key in required:
        if key not in value:
            errors.append(f"{path}.{key} is required")
            return

    properties = schema.get("properties", {})
    for key, property_schema in properties.items():
        if key in value:
            _validate(value[key], property_schema, path=f"{path}.{key}", errors=errors)
            if errors:
                return

    if schema.get("additionalProperties") is False:
        allowed = set(properties.keys())
        extra = [key for key in value if key not in allowed]
        if extra:
            errors.append(f"{path}.{extra[0]} is not allowed")


def _validate_array(value: list, schema: dict, *, path: str, errors: list[str]) -> None:
    item_schema = schema.get("items")
    if not item_schema:
        return
    for index, item in enumerate(value):
        _validate(item, item_schema, path=f"{path}[{index}]", errors=errors)
        if errors:
            return


def _matches_type(value: Any, expected_type: str | list[str]) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__
