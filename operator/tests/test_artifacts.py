"""Artifact bundle and JUnit tests (kit §5.6)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from openxr_operator.artifacts import ArtifactWriter, step_record
from openxr_operator.driver import Frame, TreeNode


def test_bundle_structure_and_junit(tmp_path: Path) -> None:
    writer = ArtifactWriter(tmp_path, flow_name="smoke")
    frame = Frame(
        image=b"\x89PNG\r\n\x1a\nfake",
        tier="t3",
        frame_id=1,
        sha256="abc123",
        width=64,
        height=36,
    )
    png = writer.save_frame(frame, "after launch")
    assert png.exists() and png.read_bytes() == frame.image
    assert "after-launch" in png.name

    tree = TreeNode("root", "Node", "/root", True, (), None, (), 3)
    tree_path = writer.save_tree(tree)
    data = json.loads(tree_path.read_text())
    assert data["children_truncated"] == 3

    steps = [
        step_record(1, "settle", "passed", 120, "settled"),
        step_record(2, "assert_visible", "failed", 5, "not visible"),
        step_record(3, "run_flow", "skipped", 0, "platform"),
    ]
    writer.write_manifest({"passed": False, "steps": len(steps)})
    junit = writer.write_junit(steps, suite="smoke")
    root = ET.parse(junit).getroot()
    assert root.attrib["tests"] == "3"
    assert root.attrib["failures"] == "1"
    assert root.attrib["errors"] == "0"
    assert root.attrib["skipped"] == "1"
    assert (writer.dir / "manifest.json").exists()
    commands = (writer.dir / "commands.jsonl").read_text().splitlines()
    assert len(commands) == 1  # the frame artifact record
    assert json.loads(commands[0])["tier"] == "t3"


def test_bundle_dirs_never_clobber(tmp_path: Path) -> None:
    a = ArtifactWriter(tmp_path, flow_name="smoke")
    b = ArtifactWriter(tmp_path, flow_name="smoke")
    assert a.dir != b.dir
