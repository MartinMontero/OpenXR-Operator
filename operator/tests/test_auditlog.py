"""Audit log integrity tests (S-08 hash chain; P3-12 redaction)."""

from __future__ import annotations

import json
from pathlib import Path

from openxr_operator.auditlog import GENESIS, AuditLog, head_hash, verify


def _log(tmp_path: Path, records: int = 3) -> Path:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    for i in range(records):
        log.append(
            {
                "flow": "smoke",
                "step": i + 1,
                "action": "set_property",
                "path": "/root/Main/StatusLabel",
                "approval": "approved",
                "frame_sha256": "ab" * 32,
                "tier": "t3",
            }
        )
    return path


def test_chain_appends_and_verifies(tmp_path: Path) -> None:
    path = _log(tmp_path)
    assert verify(path) is True
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    assert lines[0]["prev_hash"] == GENESIS
    assert lines[1]["prev_hash"] == lines[0]["record_hash"]
    assert [r["seq"] for r in lines] == [1, 2, 3]


def test_edit_detected(tmp_path: Path) -> None:
    path = _log(tmp_path)
    lines = path.read_text().splitlines()
    lines[1] = lines[1].replace("StatusLabel", "TamperedNode")
    path.write_text("\n".join(lines) + "\n")
    assert verify(path) is False


def test_midfile_deletion_detected(tmp_path: Path) -> None:
    path = _log(tmp_path)
    lines = path.read_text().splitlines()
    del lines[1]
    path.write_text("\n".join(lines) + "\n")
    assert verify(path) is False


def test_reorder_detected(tmp_path: Path) -> None:
    path = _log(tmp_path)
    lines = path.read_text().splitlines()
    lines[0], lines[1] = lines[1], lines[0]
    path.write_text("\n".join(lines) + "\n")
    assert verify(path) is False


def test_end_truncation_detected_via_head_anchor(tmp_path: Path) -> None:
    path = _log(tmp_path)
    before = head_hash(path)
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n")
    assert verify(path) is True  # remaining chain is internally valid
    assert head_hash(path) != before  # but the pinned head proves truncation


def test_resume_continues_chain(tmp_path: Path) -> None:
    path = _log(tmp_path, records=2)
    AuditLog(path).append({"flow": "smoke", "step": 3, "action": "capture"})
    assert verify(path) is True
    assert [json.loads(x)["seq"] for x in path.read_text().splitlines()] == [1, 2, 3]


def test_secrets_redacted_at_write_time(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    secret = "deadbeef" * 8
    AuditLog(path).append(
        {
            "action": "auth",
            "token": secret,
            "nested": {"api_key": secret, "ok": True},
            "note": "no secret here",
        }
    )
    raw = path.read_text()
    assert secret not in raw
    stored = json.loads(raw)
    assert stored["token"] == "[redacted]"
    assert stored["nested"]["api_key"] == "[redacted]"
    assert stored["nested"]["ok"] is True
