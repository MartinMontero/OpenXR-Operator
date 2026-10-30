"""Declarative flow parsing and validation (kit §5.4; flow YAML contract).

A flow is validated completely BEFORE any step executes: a typo fails in
milliseconds, not at step 40. `sleep` is not in the command vocabulary — its
absence is the point (settle detection replaces it). `settle.on_timeout` is
validated at parse time (S-15): invalid values are rejected, never coerced.

Header `capabilities` defaults to deny-all. Mutating flow commands
(move_controller, press) are preflighted against it at parse time, and the
driver re-checks every mutation at dispatch time (TC-SEC-004) — parse-time
preflight is UX, the driver gate is the control.

D-14: users never hand-write YAML. Flows are saved artifacts of sessions and
a power-user/regression layer. This parser is their schema gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

FLOW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["project", "scene"],
    "properties": {
        "project": {"type": "string", "minLength": 1},
        "scene": {"type": "string", "minLength": 1},
        "capture_tier": {"type": "string", "enum": ["auto", "t1", "t2", "t3"]},
        "inject_tier": {"type": "string", "enum": ["auto", "a1", "a2", "a3"]},
        "capabilities": {"type": "array", "items": {"type": "string"}},
        "env": {
            "type": "object",
            "additionalProperties": {"type": ["string", "number", "boolean"]},
        },
    },
}

# The complete command vocabulary (flow contract). Anything else — including
# sleep — is rejected at parse time.
COMMANDS = frozenset(
    {
        "launch",
        "settle",
        "assert_visible",
        "assert_property",
        "move_controller",
        "press",
        "capture",
        "run_flow",
        "repeat",
        "wait_until",
    }
)

_MUTATING_COMMANDS = frozenset({"move_controller", "press"})
_ON_TIMEOUT_VALUES = frozenset({"proceed", "fail"})
_ENV_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class FlowRejected(ValueError):
    """Flow failed parse-time validation. Nothing has executed."""


@dataclass(frozen=True)
class Flow:
    project: str
    scene: str
    capture_tier: str
    inject_tier: str
    capabilities: frozenset[str]
    env: dict[str, Any]
    commands: list[dict[str, Any]]
    path: Path


def _substitute(value: Any, env: dict[str, Any]) -> Any:
    """Recursive ${VAR} substitution; unknown variables are a parse error."""
    if isinstance(value, str):

        def _repl(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in env:
                raise FlowRejected(f"unknown env variable ${{{name}}}")
            return str(env[name])

        return _ENV_VAR.sub(_repl, value)
    if isinstance(value, list):
        return [_substitute(v, env) for v in value]
    if isinstance(value, dict):
        return {k: _substitute(v, env) for k, v in value.items()}
    return value


def _validate_command(command: dict[str, Any], capabilities: frozenset[str]) -> None:
    if len(command) != 1:
        raise FlowRejected(f"each command is a single-key mapping, got {command!r}")
    name, args = next(iter(command.items()))
    if name == "sleep":
        raise FlowRejected(
            "'sleep' is not in the command vocabulary; use 'settle' (kit §5.1)"
        )
    if name not in COMMANDS:
        raise FlowRejected(f"unknown command {name!r}; vocabulary: {sorted(COMMANDS)}")
    args = args if args is not None else {}
    if not isinstance(args, dict):
        raise FlowRejected(f"{name}: arguments must be a mapping, got {args!r}")

    if name == "settle":
        on_timeout = args.get("on_timeout", "proceed")
        if on_timeout not in _ON_TIMEOUT_VALUES:
            raise FlowRejected(
                f"settle.on_timeout {on_timeout!r} invalid; must be "
                f"{sorted(_ON_TIMEOUT_VALUES)} (S-15)"
            )
    if name in _MUTATING_COMMANDS and name not in capabilities:
        raise FlowRejected(
            f"{name} used but not granted by header capabilities "
            f"{sorted(capabilities)}; add it or remove the command"
        )
    if name == "repeat" and "commands" not in args:
        raise FlowRejected("repeat requires a 'commands' list")
    if name == "repeat":
        for sub in args["commands"]:
            _validate_command(sub, capabilities)
    if name == "run_flow" and "file" not in args:
        raise FlowRejected("run_flow requires 'file'")


def parse_flow(text: str, *, path: Path | None = None) -> Flow:
    """Parse and fully validate flow YAML text. Raises FlowRejected."""
    import jsonschema

    parts = re.split(r"^---\s*$", text, maxsplit=1, flags=re.MULTILINE)
    if len(parts) != 2:
        raise FlowRejected("flow needs a header and '---' before the command list")
    header_raw, body_raw = parts
    try:
        header = yaml.safe_load(header_raw)
        commands = yaml.safe_load(body_raw)
    except yaml.YAMLError as exc:
        raise FlowRejected(f"YAML error: {exc}") from exc

    if not isinstance(header, dict):
        raise FlowRejected("header is not a mapping")
    try:
        jsonschema.validate(header, FLOW_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise FlowRejected(f"header schema: {exc.message}") from exc
    if not isinstance(commands, list):
        raise FlowRejected("command section is not a list")

    env = dict(header.get("env", {}))
    capabilities = frozenset(header.get("capabilities", []))
    substituted = _substitute(commands, env)
    for command in substituted:
        if not isinstance(command, dict):
            raise FlowRejected(f"command entries must be mappings: {command!r}")
        _validate_command(command, capabilities)

    return Flow(
        project=str(header["project"]),
        scene=str(header["scene"]),
        capture_tier=str(header.get("capture_tier", "auto")),
        inject_tier=str(header.get("inject_tier", "auto")),
        capabilities=capabilities,
        env=env,
        commands=substituted,
        path=path if path is not None else Path("<memory>"),
    )


def load_flow(path: Path) -> Flow:
    """Load and validate a flow file. I/O happens only after a readable path."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FlowRejected(f"cannot read flow {path}: {exc}") from exc
    return parse_flow(text, path=path)
