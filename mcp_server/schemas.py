from __future__ import annotations

from typing import Any

from mcp_server.errors import MCPError


JsonSchema = dict[str, Any]


def object_schema(
    properties: dict[str, dict[str, Any]],
    required: list[str],
) -> JsonSchema:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def validate_input(schema: JsonSchema, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise MCPError(
            code="invalid_input",
            message="Tool input must be a JSON object.",
        )

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    for field in required:
        if field not in payload:
            raise MCPError(
                code="invalid_input",
                message=f"Missing required field: {field}",
                data={"field": field},
            )

    if schema.get("additionalProperties") is False:
        for field in payload:
            if field not in properties:
                raise MCPError(
                    code="invalid_input",
                    message=f"Unknown field: {field}",
                    data={"field": field},
                )

    for field, value in payload.items():
        expected_type = properties.get(field, {}).get("type")
        if expected_type is None:
            continue

        if expected_type == "string" and not isinstance(value, str):
            raise MCPError(
                code="invalid_input",
                message=f"Field must be a string: {field}",
                data={"field": field, "expected": "string"},
            )

        if expected_type == "integer" and not isinstance(value, int):
            raise MCPError(
                code="invalid_input",
                message=f"Field must be an integer: {field}",
                data={"field": field, "expected": "integer"},
            )
