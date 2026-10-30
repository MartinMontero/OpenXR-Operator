"""End-to-end runner + CLI tests against the fake engine (W3).

Full stack, executed for real: flow YAML -> parse/validate -> FlowRunner ->
GodotDriver over a real loopback WebSocket -> fake engine -> artifact bundle
+ JUnit. No model, no Godot process required.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from openxr_operator.artifacts import ArtifactWriter
from openxr_operator.cli import main
from openxr_operator.runner import FlowRunner
from tests.test_godot_driver import TOKEN, FakeEngine, _capture_reply, _driver

FLOW = """
project: ./demo_project
scene: res://scenes/main.tscn
capture_tier: t3
inject_tier: a3
capabilities: []
---
- settle: { timeout: 500 }
- assert_visible: { selector: { name: StatusLabel } }
- assert_property:
    selector: { name: StatusLabel }
    property: text
    equals: "STATUS: IDLE"
- capture: { label: after-launch }
- wait_until: { selector: { name: StatusLabel }, timeout: 300 }
- run_flow: { file: sub.yaml }
- run_flow: { file: sub.yaml, when: { platform: amiga } }
"""

SUB = """
project: p
scene: s
---
- settle: {}
"""


@pytest.fixture
def engine(tmp_path: Path):
    png = tmp_path / "frame.png"
    Image.new("RGB", (64, 36), (10, 20, 30)).save(png)
    e = FakeEngine(capture=_capture_reply(png))
    yield e
    e.stop()


def _write_flows(tmp_path: Path, text: str = FLOW) -> Path:
    (tmp_path / "sub.yaml").write_text(SUB)
    path = tmp_path / "main.yaml"
    path.write_text(text)
    return path


def test_full_flow_passes_with_bundle(engine: FakeEngine, tmp_path: Path) -> None:
    from openxr_operator.flow import load_flow

    flow = load_flow(_write_flows(tmp_path))
    driver = _driver(engine, capture_tier="t3")
    writer = ArtifactWriter(tmp_path / "runs", flow_name="main")
    report = FlowRunner(driver, writer).run(flow)
    driver.close()

    assert report.passed, [s for s in report.steps if s["status"] != "passed"]
    statuses = [s["status"] for s in report.steps]
    assert statuses.count("passed") == 6  # 5 main steps + the subflow
    assert statuses.count("skipped") == 1  # the amiga-only subflow
    assert (report.bundle / "junit.xml").exists()
    assert list((report.bundle / "frames").glob("*.png"))
    assert list((report.bundle / "trees").glob("*.json"))
    root = ET.parse(report.bundle / "junit.xml").getroot()
    assert root.attrib["failures"] == "0"
    assert root.attrib["skipped"] == "1"


def test_failing_step_stops_run_and_is_recorded(
    engine: FakeEngine, tmp_path: Path
) -> None:
    from openxr_operator.flow import load_flow

    bad = "project: p\nscene: s\n---\n- assert_visible: { selector: { name: NoSuchNode } }\n- capture: {}\n"
    (tmp_path / "bad.yaml").write_text(bad)
    flow = load_flow(tmp_path / "bad.yaml")
    driver = _driver(engine, capture_tier="t3")
    writer = ArtifactWriter(tmp_path / "runs", flow_name="bad")
    report = FlowRunner(driver, writer).run(flow)
    driver.close()

    assert not report.passed
    assert len(report.steps) == 1  # capture never ran
    assert report.steps[0]["status"] == "error"
    root = ET.parse(report.bundle / "junit.xml").getroot()
    assert root.attrib["errors"] == "1"


def test_cli_end_to_end(engine: FakeEngine, tmp_path: Path) -> None:
    flow = _write_flows(tmp_path)
    token = tmp_path / "engine.token"
    token.write_text(TOKEN)
    rc = main(
        [
            "run",
            str(flow),
            "--token-file",
            str(token),
            "--port",
            str(engine.port),
            "--capture-tier",
            "t3",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--no-model",
        ]
    )
    assert rc == 0


def test_cli_rejects_missing_flow(tmp_path: Path) -> None:
    token = tmp_path / "engine.token"
    token.write_text(TOKEN)
    rc = main(["run", str(tmp_path / "nope.yaml"), "--token-file", str(token)])
    assert rc == 2
