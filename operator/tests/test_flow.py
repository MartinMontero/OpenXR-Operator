"""Flow parsing/validation tests (kit §5.4; S-15; flow YAML contract)."""

from __future__ import annotations

from pathlib import Path

import pytest

from openxr_operator.flow import FlowRejected, load_flow, parse_flow

SMOKE = Path(__file__).parents[2] / "flows" / "smoke.yaml"

VALID = """
project: ./demo_project
scene: res://scenes/main.tscn
capture_tier: t3
inject_tier: a3
capabilities: [move_controller, press]
env:
  CUBE: Main/GrabbableCube
---
- launch: { clean: true }
- settle: { timeout: 8000, on_timeout: fail }
- assert_visible:
    selector: { name: "${CUBE}", class: RigidBody3D }
- move_controller:
    hand: right
    position: [0.2, 1.2, -0.4]
    rotation: [0, 0, 0, 1]
- press: { hand: right, action: grab, value: 1.0 }
- capture: { label: after-grab }
- repeat:
    times: 2
    commands:
      - settle: {}
- run_flow:
    file: subflows/verify.yaml
    when: { platform: linux }
"""


def test_repo_smoke_flow_parses_deny_all() -> None:
    flow = load_flow(SMOKE)
    assert flow.project == "./demo_project"
    assert flow.capture_tier == "t3"
    assert flow.capabilities == frozenset()  # deny-all default
    assert [next(iter(c)) for c in flow.commands] == ["launch", "settle", "capture"]


def test_valid_full_flow_with_env_substitution() -> None:
    flow = parse_flow(VALID)
    selector = flow.commands[2]["assert_visible"]["selector"]
    assert selector["name"] == "Main/GrabbableCube"
    assert flow.capabilities == frozenset({"move_controller", "press"})
    assert flow.commands[1]["settle"]["on_timeout"] == "fail"


def test_sleep_is_not_in_the_vocabulary() -> None:
    with pytest.raises(FlowRejected, match="sleep"):
        parse_flow("project: p\nscene: s\n---\n- sleep: 2\n")


def test_unknown_command_rejected() -> None:
    with pytest.raises(FlowRejected, match="unknown command"):
        parse_flow("project: p\nscene: s\n---\n- teleport: {}\n")


def test_settle_on_timeout_validated_at_parse_time_s15() -> None:
    with pytest.raises(FlowRejected, match="on_timeout"):
        parse_flow("project: p\nscene: s\n---\n- settle: { on_timeout: maybe }\n")


def test_mutating_command_requires_capability() -> None:
    with pytest.raises(FlowRejected, match="capabilities"):
        parse_flow("project: p\nscene: s\n---\n- press: { hand: right, action: grab, value: 1.0 }\n")


def test_nested_repeat_commands_validated() -> None:
    with pytest.raises(FlowRejected, match="capabilities"):
        parse_flow(
            "project: p\nscene: s\n---\n"
            "- repeat:\n    times: 3\n    commands:\n"
            "      - press: { hand: right, action: grab, value: 1.0 }\n"
        )


def test_header_schema_rejects_bad_tier() -> None:
    with pytest.raises(FlowRejected, match="header schema"):
        parse_flow("project: p\nscene: s\ncapture_tier: t9\n---\n- settle: {}\n")


def test_missing_separator_rejected() -> None:
    with pytest.raises(FlowRejected, match="---"):
        parse_flow("project: p\nscene: s\n")


def test_unknown_env_variable_rejected() -> None:
    with pytest.raises(FlowRejected, match="unknown env"):
        parse_flow('project: p\nscene: s\n---\n- capture: { label: "${NOPE}" }\n')


def test_repeat_requires_commands() -> None:
    with pytest.raises(FlowRejected, match="repeat"):
        parse_flow("project: p\nscene: s\n---\n- repeat: { times: 2 }\n")


def test_run_flow_requires_file() -> None:
    with pytest.raises(FlowRejected, match="run_flow"):
        parse_flow("project: p\nscene: s\n---\n- run_flow: { when: { platform: linux } }\n")
