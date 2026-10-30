"""Diff-then-approve gate with D-14 plain-language summaries (kit §3.4).

No file write, property change, script assignment, injection, or scene restart
executes without a human seeing a summary and approving it. The approval
surface speaks plain language: a non-developer can judge every proposed
mutation. Raw JSON is never the approval view; the model's rationale is shown
as a *quote from an untrusted source*, not as truth.

D-06: there is no auto-approve switch in v1. Rejections are recorded with the
proposed diff, exactly like approvals — the audit log must be able to answer
"what did the agent try to do, and who allowed it?"
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("openxr_operator.approval")


@dataclass(frozen=True)
class PlainLanguageDiff:
    """What the human actually reviews. No raw JSON in this view."""

    title: str
    lines: tuple[str, ...]
    rationale: str  # the model's stated reason, quoted and labelled untrusted
    action: dict[str, Any] = field(repr=False)  # for the audit record, not the UI


@dataclass(frozen=True)
class ApprovalRecord:
    approved: bool
    diff: PlainLanguageDiff
    decided_at: str
    approver: str = "human"


def summarize(action: dict[str, Any]) -> PlainLanguageDiff:
    """Render one validated action as a plain-language review card."""
    kind = action.get("action")
    rationale = str(action.get("rationale", ""))
    lines: tuple[str, ...]
    if kind == "set_property":
        title = "Change a property in your scene"
        lines = (
            f"Node: {action.get('path')}",
            f'Set "{action.get("property")}" to: {_short(action.get("value"))}',
        )
    elif kind == "write_code":
        code = str(action.get("code", ""))
        title = "Write a script file"
        lines = (
            f"File: {action.get('file_path')}",
            f"Size: {len(code.splitlines())} lines",
            "The full script is shown below this card for review.",
        )
    elif kind == "assign_script":
        title = "Attach a script to a node"
        lines = (
            f"Node: {action.get('path')}",
            f"Script: {action.get('script_path')}",
        )
    elif kind == "move_controller":
        title = f"Move the {action.get('hand')} controller"
        lines = (
            f"New position: {action.get('position')}",
            f"New rotation: {action.get('rotation')}",
        )
    elif kind == "press":
        title = f'Press "{action.get("action_name")}" on the {action.get("hand")} controller'
        lines = (f"Strength: {action.get('float_value')}",)
    elif kind == "restart_scene":
        title = "Restart the current scene"
        lines = ("Anything unsaved in the running scene is lost.",)
    else:
        title = f"Action: {kind}"
        lines = (str({k: v for k, v in action.items() if k != "rationale"}),)
    return PlainLanguageDiff(
        title=title, lines=lines, rationale=rationale, action=action
    )


def _short(value: Any, limit: int = 120) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


class ApprovalGate:
    """The unbypassable gate. Every mutating action needs an ApprovalRecord."""

    def request(
        self,
        action: dict[str, Any],
        *,
        decide: Callable[[PlainLanguageDiff], bool],
    ) -> ApprovalRecord:
        """Present the plain-language diff; record the human's decision.

        ``decide`` is the human surface (CLI prompt, web UI dialog, or a test
        double). It returns True to approve, False to reject. The rejection
        record carries the proposed diff, so nothing is tried invisibly.
        """
        diff = summarize(action)
        approved = bool(decide(diff))
        record = ApprovalRecord(
            approved=approved,
            diff=diff,
            decided_at=datetime.now(UTC).isoformat(),
        )
        logger.info(
            "approval decision: %s action=%s title=%r",
            "APPROVED" if approved else "REJECTED",
            action.get("action"),
            diff.title,
        )
        return record


def render_card(diff: PlainLanguageDiff) -> str:
    """Text rendering shared by the CLI prompt and the web UI."""
    body = "\n".join(f"  {line}" for line in diff.lines)
    rationale = diff.rationale or "(none given)"
    return (
        f"{diff.title}\n{body}\n\n"
        f"Why the agent says it wants to do this (its words, not verified):\n"
        f"  {rationale}\n"
    )
