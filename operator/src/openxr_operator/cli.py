"""OpenXR Operator CLI (pyproject entry point: openxr-operator).

    openxr-operator run flows/smoke.yaml --token-file <path> [--godot <binary>]

Runs a validated flow deterministically (the model is a client, not a
component — no model is contacted by `run`). Exit code 0 only when every step
passed; the run bundle lands under --runs-dir either way.
"""

from __future__ import annotations

import argparse
import logging
import secrets
import sys
from pathlib import Path

from .agent import AgentLoop
from .approval import ApprovalGate
from .artifacts import ArtifactWriter
from .auditlog import AuditLog
from .backends import ModelUnreachable, resolve
from .flow import FlowRejected, load_flow
from .godot_driver import DriverError, GodotDriver, read_token
from .runner import FlowRunner
from .selectors import SelectorError
from .ui.app import serve
from .ui.runtime import UIRuntime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openxr-operator")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a flow deterministically (no model)")
    run.add_argument("flow", type=Path)
    run.add_argument("--token-file", type=Path, required=True)
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=9099)
    run.add_argument("--godot", help="engine binary, if the flow launches a process")
    run.add_argument("--runs-dir", type=Path, default=Path("runs"))
    run.add_argument("--capture-tier", choices=["t1", "t2", "t3"])
    run.add_argument(
        "--no-model",
        action="store_true",
        help="accepted for CI clarity; `run` never contacts a model",
    )
    ui = sub.add_parser("ui", help="start the loopback web UI (D-14 surface)")
    ui.add_argument("--token-file", type=Path, required=True, help="engine token file")
    ui.add_argument("--project", required=True, help="Godot project directory")
    ui.add_argument("--godot", help="engine binary (optional)")
    ui.add_argument("--port", type=int, default=9099, help="engine port")
    ui.add_argument("--ui-port", type=int, default=5000, help="web UI port (loopback)")
    ui.add_argument("--backend", default="local_ollama")
    ui.add_argument("--model", default="qwen2.5vl:7b")
    ui.add_argument("--model-host", default="http://127.0.0.1:11434")
    ui.add_argument("--capabilities", default="set_property,write_code")
    ui.add_argument("--runs-dir", type=Path, default=Path("runs"))
    args = parser.parse_args(argv)

    if args.command == "ui":
        return _run_ui(args)

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    try:
        flow = load_flow(args.flow)
        driver = GodotDriver(
            host=args.host,
            port=args.port,
            capabilities=flow.capabilities,
            capture_tier=args.capture_tier,
            godot_binary=args.godot,
            project=flow.project,
        )
        driver.connect(token=read_token(args.token_file))
        try:
            artifacts = ArtifactWriter(args.runs_dir, flow_name=flow.path.stem)
            report = FlowRunner(driver, artifacts).run(flow)
        finally:
            driver.shutdown()
    except (FlowRejected, SelectorError, DriverError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failed = [s for s in report.steps if s["status"] in ("failed", "error")]
    print(f"bundle: {report.bundle}")
    print(f"junit:  {report.bundle / 'junit.xml'}")
    if failed:
        for step in failed:
            print(f"FAILED step {step['index']} {step['command']}: {step['detail']}")
        return 1
    print(f"PASS: {len(report.steps)} steps, all green")
    return 0


def _run_ui(args: argparse.Namespace) -> int:
    """Wire engine + local backend + agent loop into the loopback web UI."""
    capabilities = frozenset(
        part.strip() for part in args.capabilities.split(",") if part.strip()
    )
    try:
        driver = GodotDriver(
            port=args.port,
            capabilities=capabilities,
            godot_binary=args.godot,
            project=args.project,
        )
        driver.connect(token=read_token(args.token_file))
        backend = resolve(
            {
                "backend": args.backend,
                "model": args.model,
                "host": args.model_host,
                "egress": {"allow": []},
            }
        )
    except (DriverError, ModelUnreachable) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    artifacts = ArtifactWriter(args.runs_dir, flow_name="ui")
    loop = AgentLoop(
        driver,
        backend,
        ApprovalGate(),
        AuditLog(args.runs_dir / "audit.jsonl"),
        artifacts,
        project_root=Path(args.project).resolve(),
        capabilities=capabilities,
    )
    ui_token = secrets.token_hex(16)
    print("OpenXR Operator UI (loopback only). Open this URL in your browser:")
    print(f"  http://127.0.0.1:{args.ui_port}/?token={ui_token}")
    print("Keep this token private. Ctrl-C stops the server.")
    serve(UIRuntime(loop), ui_token=ui_token, port=args.ui_port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
