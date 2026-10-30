"""Approval gate tests (D-14 plain language; D-06 no auto-approve)."""

from __future__ import annotations

import logging

import pytest

from openxr_operator.approval import (
    ApprovalGate,
    PlainLanguageDiff,
    render_card,
    summarize,
)


def _set_property() -> dict:
    return {
        "action": "set_property",
        "rationale": "The user asked for a red status label",
        "path": "/root/Main/StatusLabel",
        "property": "text",
        "value": "STATUS: RED",
    }


def test_summary_is_plain_language_not_json() -> None:
    diff = summarize(_set_property())
    assert diff.title == "Change a property in your scene"
    assert any("StatusLabel" in line for line in diff.lines)
    assert any('"text"' in line and "STATUS: RED" in line for line in diff.lines)
    card = render_card(diff)
    assert "its words, not verified" in card
    assert "The user asked for a red status label" in card


def test_gate_approval_recorded() -> None:
    gate = ApprovalGate()
    seen: list[PlainLanguageDiff] = []
    record = gate.request(_set_property(), decide=lambda d: seen.append(d) or True)
    assert record.approved is True
    assert record.approver == "human"
    assert seen and seen[0].title == record.diff.title


def test_gate_rejection_recorded_with_diff(caplog: pytest.LogCaptureFixture) -> None:
    gate = ApprovalGate()
    with caplog.at_level(logging.INFO, logger="openxr_operator.approval"):
        record = gate.request(_set_property(), decide=lambda d: False)
    assert record.approved is False
    assert record.diff.action["value"] == "STATUS: RED"  # rejected diff preserved
    assert "REJECTED" in caplog.text


@pytest.mark.parametrize(
    "action",
    [
        {
            "action": "write_code",
            "rationale": "r",
            "file_path": "a.gd",
            "code": "x\ny\n",
        },
        {
            "action": "assign_script",
            "rationale": "r",
            "path": "/root/A",
            "script_path": "a.gd",
        },
        {
            "action": "move_controller",
            "rationale": "r",
            "hand": "right",
            "position": [0, 1, 0],
            "rotation": [0, 0, 0, 1],
        },
        {
            "action": "press",
            "rationale": "r",
            "hand": "left",
            "action_name": "grab",
            "float_value": 1.0,
        },
        {"action": "restart_scene", "rationale": "r"},
    ],
)
def test_every_mutating_kind_renders_a_review_card(action: dict) -> None:
    diff = summarize(action)
    assert diff.title
    assert diff.lines
    assert "rationale" not in diff.lines  # rationale is quoted separately, untrusted


def test_no_auto_approve_switch_d06() -> None:
    gate = ApprovalGate()
    assert not hasattr(gate, "auto_approve")
    assert not hasattr(gate, "bypass")
