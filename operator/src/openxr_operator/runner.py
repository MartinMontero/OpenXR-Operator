"""Flow runner (kit §5.4/§5.6): executes validated flows against a Driver.

The model is a client, not a component: this runner is a deterministic test
harness with the agent turned off, and its suite passes with no backend at
all. Every step is recorded with its outcome and timing; settle outcomes are
recorded per step (a flow whose steps are all TIMEOUT_PROCEED is not actually
synchronising); a failing step stops the run and the bundle still lands.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import ArtifactWriter, step_record
from .driver import Driver, TreeNode
from .flow import Flow, load_flow
from .godot_driver import DriverError
from .selectors import SelectorError, resolve_selector
from .settle import SettleOutcome, wait_for_settle

logger = logging.getLogger("openxr_operator.runner")


@dataclass(frozen=True)
class RunReport:
    steps: list[dict[str, Any]]
    bundle: Path

    @property
    def passed(self) -> bool:
        return all(s["status"] in ("passed", "skipped") for s in self.steps)


class FlowRunner:
    def __init__(self, driver: Driver, artifacts: ArtifactWriter) -> None:
        self._driver = driver
        self._artifacts = artifacts
        self._steps: list[dict[str, Any]] = []

    def run(self, flow: Flow) -> RunReport:
        self._steps = []
        for i, command in enumerate(flow.commands, 1):
            if not self._execute(i, command, flow):
                break
        self._artifacts.write_manifest(
            {
                "flow": str(flow.path),
                "project": flow.project,
                "scene": flow.scene,
                "capture_tier": flow.capture_tier,
                "inject_tier": flow.inject_tier,
                "capabilities": sorted(flow.capabilities),
                "platform": sys.platform,
                "passed": self.passed,
                "steps": len(self._steps),
            }
        )
        self._artifacts.write_junit(self._steps, suite=flow.path.stem)
        return RunReport(steps=self._steps, bundle=self._artifacts.dir)

    @property
    def passed(self) -> bool:
        return all(s["status"] in ("passed", "skipped") for s in self._steps)

    def _record(
        self,
        index: int,
        name: str,
        status: str,
        started: float,
        detail: str = "",
        **extra: Any,
    ) -> None:
        duration = int((time.monotonic() - started) * 1000)
        record = step_record(index, name, status, duration, detail, **extra)
        self._steps.append(record)
        self._artifacts.record_command(record)
        logger.info("step %d %s: %s %s", index, name, status, detail)

    def _execute(self, index: int, command: dict[str, Any], flow: Flow) -> bool:
        """Execute one command; False means stop the run."""
        name, args = next(iter(command.items()))
        args = args or {}
        started = time.monotonic()
        try:
            detail, extra = self._dispatch(name, args, flow)
            status = "skipped" if detail.startswith("skipped") else "passed"
            self._record(index, name, status, started, detail, **extra)
            return True
        except (SelectorError, DriverError, AssertionError) as exc:
            status = "failed" if isinstance(exc, AssertionError) else "error"
            self._record(index, name, status, started, str(exc))
            return False

    def _dispatch(
        self, name: str, args: dict[str, Any], flow: Flow
    ) -> tuple[str, dict[str, Any]]:
        if name == "launch":
            self._driver.launch(flow.scene, clean=bool(args.get("clean", False)))
            return flow.scene, {}
        if name == "settle":
            return self._settle(args)
        if name == "assert_visible":
            return self._assert_visible(args)
        if name == "assert_property":
            return self._assert_property(args)
        if name == "capture":
            frame = self._driver.capture()
            path = self._artifacts.save_frame(frame, str(args.get("label", "frame")))
            return f"{path.name} tier={frame.tier}", {"tier": frame.tier}
        if name == "move_controller":
            self._driver.move_controller(
                args["hand"], tuple(args["position"]), tuple(args["rotation"])
            )
            return f"{args['hand']} moved", {}
        if name == "press":
            self._driver.press(args["hand"], args["action"], float(args["value"]))
            return f"{args['hand']} {args['action']}={args['value']}", {}
        if name == "wait_until":
            return self._wait_until(args)
        if name == "run_flow":
            return self._run_subflow(args, flow)
        if name == "repeat":
            for _ in range(int(args.get("times", 1))):
                for sub in args["commands"]:
                    sub_name, sub_args = next(iter(sub.items()))
                    self._dispatch(sub_name, sub_args or {}, flow)
            return f"times={args.get('times', 1)}", {}
        raise AssertionError(f"validated command not implemented: {name}")

    def _settle(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        result = wait_for_settle(
            lambda: self._driver.capture().image,
            timeout_ms=int(args.get("timeout", 5000)),
            on_timeout=str(args.get("on_timeout", "proceed")),
        )
        detail = f"{result.outcome.value} in {result.elapsed_ms} ms"
        if result.outcome is SettleOutcome.TIMEOUT_FAIL:
            raise AssertionError(f"settle timeout (fail mode): {detail}")
        return detail, {"settle_outcome": result.outcome.value}

    def _tree(self) -> TreeNode:
        tree = self._driver.scene_tree()
        self._artifacts.save_tree(tree)
        return tree

    def _assert_visible(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        selector = args["selector"]
        node = resolve_selector(self._tree(), selector)
        if node is None:
            return "absent as allowed (optional)", {}
        if not node.visible:
            raise AssertionError(f"{node.path} exists but is not visible")
        return node.path, {}

    def _assert_property(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        node = resolve_selector(self._tree(), args["selector"])
        assert node is not None
        value = self._driver.get_property(node.path, args["property"])
        if "equals" in args and value != args["equals"]:
            raise AssertionError(
                f"{node.path}.{args['property']} = {value!r}, "
                f"expected {args['equals']!r}"
            )
        return f"{node.path}.{args['property']} = {value!r}", {}

    def _wait_until(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        timeout_ms = int(args.get("timeout", 5000))
        interval_ms = int(args.get("interval", 100))
        selector = dict(args["selector"]) | {"optional": True}
        deadline = time.monotonic() + timeout_ms / 1000.0
        wake = threading.Event()
        while True:
            node = resolve_selector(self._tree(), selector)
            if node is not None and node.visible:
                return f"condition met: {node.path}", {}
            if time.monotonic() >= deadline:
                raise AssertionError(f"wait_until timed out after {timeout_ms} ms")
            wake.wait(timeout=interval_ms / 1000.0)

    def _run_subflow(
        self, args: dict[str, Any], flow: Flow
    ) -> tuple[str, dict[str, Any]]:
        when = args.get("when", {})
        platform = when.get("platform")
        if platform:
            current = "linux" if sys.platform.startswith("linux") else sys.platform
            if current != platform and not (
                platform == "windows" and sys.platform == "win32"
            ):
                return f"skipped (platform {platform} != {sys.platform})", {}
        sub_path = flow.path.parent / args["file"]
        sub = load_flow(sub_path)
        for command in sub.commands:
            name, sub_args = next(iter(command.items()))
            self._dispatch(name, sub_args or {}, sub)
        return f"subflow {sub_path.name}", {}
