"""Agent loop tests: model -> validate -> approve -> execute -> audit.

The model is a scripted fake backend; the engine is the fake WebSocket
server; the human is a decide() test double. Every claim is checked against
the wire log and the audit chain, not against the loop's own narration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from openxr_operator.agent import AgentLoop
from openxr_operator.approval import ApprovalGate, PlainLanguageDiff
from openxr_operator.artifacts import ArtifactWriter
from openxr_operator.auditlog import AuditLog, verify
from openxr_operator.model import Capabilities, ModelResponse
from tests.test_godot_driver import FakeEngine, _capture_reply, _driver

SET_RED = {
    "action": "set_property",
    "rationale": "User wants red",
    "path": "/root/Main/StatusLabel",
    "property": "text",
    "value": "STATUS: RED",
}
FINISH = {"action": "finish", "rationale": "done", "summary": "Label is red."}


class FakeBackend:
    backend_id = "fake"

    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self._actions = list(actions)
        self.calls = 0

    def capabilities(self) -> Capabilities:
        return Capabilities("native", True, 8, "local", None)

    def health(self) -> bool:
        return True

    def act(self, system, task, scene_tree, image_paths, schema) -> ModelResponse:  # type: ignore[no-untyped-def]
        self.calls += 1
        action = self._actions.pop(0) if self._actions else FINISH
        return ModelResponse(
            raw=json.dumps(action),
            parsed=action,
            model="fake-1b",
            backend_id="fake",
            constraint="native",
            duration_ns=1,
        )


@pytest.fixture
def engine(tmp_path: Path):
    png = tmp_path / "frame.png"
    Image.new("RGB", (64, 36), (10, 20, 30)).save(png)
    e = FakeEngine(capture=_capture_reply(png))
    yield e
    e.stop()


def _loop(
    engine: FakeEngine,
    tmp_path: Path,
    actions: list[dict[str, Any]],
    capabilities=frozenset({"set_property"}),
) -> AgentLoop:
    driver = _driver(engine, capabilities=capabilities, capture_tier="t3")
    return AgentLoop(
        driver,
        FakeBackend(actions),
        ApprovalGate(),
        AuditLog(tmp_path / "runs" / "audit.jsonl"),
        ArtifactWriter(tmp_path / "runs", flow_name="agent"),
        project_root=tmp_path,
        capabilities=capabilities,
    )


def test_approved_mutation_executes_and_audits(
    engine: FakeEngine, tmp_path: Path
) -> None:
    loop = _loop(engine, tmp_path, [SET_RED, FINISH])
    report = loop.run_task("make the label red", decide=lambda d: True)
    assert report.outcome == "finished"
    assert report.summary == "Label is red."
    # the mutation really reached the engine
    assert any(m.get("cmd") == "set_property" for m in engine.received)
    # audit chain is intact and names the approval + execution
    assert verify(tmp_path / "runs" / "audit.jsonl") is True
    events = [r.get("event") for r in _audit_records(tmp_path)]
    assert "approval" in events and "executed" in events


def test_rejection_never_reaches_wire_and_is_recorded(
    engine: FakeEngine, tmp_path: Path
) -> None:
    loop = _loop(engine, tmp_path, [SET_RED, FINISH])
    report = loop.run_task("make the label red", decide=lambda d: False)
    assert report.outcome == "finished"
    assert not any(m.get("cmd") == "set_property" for m in engine.received)
    events = [r for r in _audit_records(tmp_path) if r.get("event") == "approval"]
    assert events and events[0]["approved"] is False


def test_capability_violation_retries_once_then_aborts_no_gate_call(
    engine: FakeEngine, tmp_path: Path
) -> None:
    loop = _loop(engine, tmp_path, [SET_RED, SET_RED], capabilities=frozenset())
    called: list[PlainLanguageDiff] = []
    report = loop.run_task(
        "make the label red", decide=lambda d: called.append(d) or True
    )
    assert report.outcome == "aborted"
    assert called == []  # the human is never asked about an illegal action
    assert not any(m.get("cmd") == "set_property" for m in engine.received)
    rejected = [
        r for r in _audit_records(tmp_path) if r.get("event") == "validation_rejected"
    ]
    assert len(rejected) == 2  # exactly one retry, then abort


def test_write_code_containment_blocks_traversal_before_human(
    engine: FakeEngine, tmp_path: Path
) -> None:
    evil = {
        "action": "write_code",
        "rationale": "escape",
        "file_path": "../outside.gd",
        "code": "extends Node\n",
    }
    loop = _loop(engine, tmp_path, [evil], capabilities=frozenset({"write_code"}))
    report = loop.run_task("write outside", decide=lambda d: True)
    assert report.outcome == "aborted"
    assert "containment" in report.summary
    assert not (tmp_path.parent / "outside.gd").exists()


def test_write_code_allowed_writes_contained_file(
    engine: FakeEngine, tmp_path: Path
) -> None:
    good = {
        "action": "write_code",
        "rationale": "new script",
        "file_path": "scripts/hello.gd",
        "code": "extends Node\n",
    }
    loop = _loop(
        engine, tmp_path, [good, FINISH], capabilities=frozenset({"write_code"})
    )
    report = loop.run_task("write a script", decide=lambda d: True)
    assert report.outcome == "finished"
    assert (tmp_path / "scripts" / "hello.gd").read_text() == "extends Node\n"


def _audit_records(tmp_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (tmp_path / "runs" / "audit.jsonl").read_text().splitlines()
    ]
