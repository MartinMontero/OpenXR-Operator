"""Run artifact bundles and JUnit output (kit §5.6).

Every run writes a directory whether it passed or failed: manifest.json,
commands.jsonl (one record per step), frames/, trees/, and junit.xml. The
bundle is the forensic record — when a step goes wrong, the interesting
question is what the driver actually saw and did, and reconstructing that
after the fact is impossible.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .driver import Frame, TreeNode


def tree_to_dict(node: TreeNode) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": node.name,
        "class": node.cls,
        "path": node.path,
        "visible": node.visible,
        "groups": list(node.groups),
        "children": [tree_to_dict(c) for c in node.children],
    }
    if node.text is not None:
        out["text"] = node.text
    if node.truncated_children:
        out["children_truncated"] = node.truncated_children
    return out


class ArtifactWriter:
    """Writes one run bundle under ``runs/`` (or a caller-chosen base)."""

    def __init__(self, base: Path, *, flow_name: str) -> None:
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
        self.dir = base / f"{stamp}-{flow_name}"
        suffix = 1
        while self.dir.exists():
            suffix += 1
            self.dir = base / f"{stamp}-{flow_name}-{suffix}"
        for sub in ("frames", "trees", "model"):
            (self.dir / sub).mkdir(parents=True)
        self._commands_path = self.dir / "commands.jsonl"
        self._frames = 0
        self._trees = 0

    def record_command(self, record: dict[str, Any]) -> None:
        """Append one step record (command, resolution, timing, outcome)."""
        with self._commands_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def save_frame(self, frame: Frame, label: str) -> Path:
        self._frames += 1
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in label)
        path = self.dir / "frames" / f"{self._frames:04d}-{safe}.png"
        path.write_bytes(frame.image)
        self.record_command(
            {
                "artifact": "frame",
                "path": str(path),
                "tier": frame.tier,
                "sha256": frame.sha256,
                "frame_id": frame.frame_id,
            }
        )
        return path

    def save_tree(self, tree: TreeNode) -> Path:
        self._trees += 1
        path = self.dir / "trees" / f"{self._trees:04d}.json"
        path.write_text(json.dumps(tree_to_dict(tree), indent=2), encoding="utf-8")
        return path

    def write_manifest(self, manifest: dict[str, Any]) -> None:
        (self.dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def write_junit(self, steps: list[dict[str, Any]], *, suite: str) -> Path:
        """JUnit XML because that is what CI consumes."""
        failures = sum(1 for s in steps if s["status"] == "failed")
        errors = sum(1 for s in steps if s["status"] == "error")
        skipped = sum(1 for s in steps if s["status"] == "skipped")
        root = ET.Element(
            "testsuite",
            {
                "name": suite,
                "tests": str(len(steps)),
                "failures": str(failures),
                "errors": str(errors),
                "skipped": str(skipped),
            },
        )
        for i, step in enumerate(steps, 1):
            case = ET.SubElement(
                root,
                "testcase",
                {
                    "name": f"{i:03d}-{step['command']}",
                    "time": f"{step['duration_ms'] / 1000:.3f}",
                },
            )
            if step["status"] in ("failed", "error"):
                tag = "failure" if step["status"] == "failed" else "error"
                el = ET.SubElement(case, tag, {"message": step.get("detail", "")})
                el.text = step.get("detail", "")
            elif step["status"] == "skipped":
                ET.SubElement(case, "skipped")
        ET.indent(root)
        path = self.dir / "junit.xml"
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return path


@dataclass(frozen=True)
class StepRecord:
    index: int
    command: str
    status: str
    duration_ms: int
    detail: str


def step_record(
    index: int,
    command: str,
    status: str,
    duration_ms: int,
    detail: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Uniform step record shape shared by the runner and the JUnit emitter."""
    return asdict(StepRecord(index, command, status, duration_ms, detail)) | extra
