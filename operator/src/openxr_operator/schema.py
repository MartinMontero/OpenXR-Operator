"""Action schema (FROZEN contract — orchestrator-owned).

Single source of truth for the action contract: passed to the model as
`format` AND used to validate the result. One definition, two uses —
they cannot drift. Fixes v2.0 finding F-004.
"""

from __future__ import annotations

from typing import Any

READ_ONLY_ACTIONS = frozenset({"observe", "assert_property", "finish"})
MUTATING_ACTIONS = frozenset(
    {
        "set_property",
        "write_code",
        "assign_script",
        "move_controller",
        "press",
        "restart_scene",
    }
)
ALL_ACTIONS = READ_ONLY_ACTIONS | MUTATING_ACTIONS

ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "rationale"],
    "properties": {
        "action": {"type": "string", "enum": sorted(ALL_ACTIONS)},
        "rationale": {"type": "string", "maxLength": 500},
        "path": {"type": "string", "maxLength": 512},
        "property": {"type": "string", "maxLength": 128},
        "value": {},
        "file_path": {"type": "string", "maxLength": 512},
        "code": {"type": "string", "maxLength": 65536},
        "script_path": {"type": "string", "maxLength": 512},
        "hand": {"type": "string", "enum": ["left", "right"]},
        "action_name": {"type": "string", "maxLength": 64},
        "position": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 3,
            "maxItems": 3,
        },
        "rotation": {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 4,
            "maxItems": 4,
        },
        "float_value": {"type": "number", "minimum": -1.0, "maximum": 1.0},
        "summary": {"type": "string", "maxLength": 1000},
    },
}

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "set_property": ("path", "property", "value"),
    "write_code": ("file_path", "code"),
    "assign_script": ("path", "script_path"),
    "move_controller": ("hand", "position", "rotation"),
    "press": ("hand", "action_name", "float_value"),
    "assert_property": ("path", "property", "value"),
    "restart_scene": (),
    "observe": (),
    "finish": ("summary",),
}


class ActionRejected(ValueError):
    pass


def validate_action(
    obj: dict[str, Any], capabilities: frozenset[str]
) -> dict[str, Any]:
    """Validate shape, then capability. Raises ActionRejected."""
    import jsonschema

    try:
        jsonschema.validate(obj, ACTION_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise ActionRejected(f"schema: {exc.message}") from exc
    action = obj["action"]
    for field in _REQUIRED_FIELDS[action]:
        if field not in obj:
            raise ActionRejected(f"{action} requires '{field}'")
    if action in MUTATING_ACTIONS and action not in capabilities:
        raise ActionRejected(
            f"'{action}' not granted by flow capabilities {sorted(capabilities)}"
        )
    return obj


def is_mutating(action: str) -> bool:
    return action in MUTATING_ACTIONS
