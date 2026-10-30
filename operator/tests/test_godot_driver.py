"""Driver tests against a fake in-process engine (W2-02-operator-driver).

No real Godot required: the fake speaks wire protocol v2 over a real loopback
WebSocket, records every frame it receives, and lets each test script the
replies. TC-SEC-004 asserts on that record: a rejected mutation must leave
nothing but the auth frame on the wire.
"""

from __future__ import annotations

import hashlib
import json
import logging
import socket
import threading
from pathlib import Path
from typing import Any

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import ServerConnection, serve

from openxr_operator.godot_driver import (
    AuthError,
    CaptureVerificationError,
    DriverError,
    GodotDriver,
    ProtocolError,
    TrackerBindError,
    read_token,
)
from openxr_operator.schema import ActionRejected

TOKEN = "a" * 64
TREE = json.loads(
    (Path(__file__).parent / "fixtures" / "demo_scene_tree.json").read_text()
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class FakeEngine:
    """Wire-protocol v2 server with scripted replies and a received-frame log."""

    def __init__(
        self,
        *,
        token: str = TOKEN,
        reply_protocol: int = 2,
        capture: dict[str, Any] | None = None,
        inject_ok: bool = True,
        wrong_id_once: bool = False,
    ) -> None:
        self.token = token
        self.reply_protocol = reply_protocol
        self.capture = capture
        self.inject_ok = inject_ok
        self.wrong_id_once = wrong_id_once
        self.received: list[dict[str, Any]] = []
        self.port = _free_port()
        self.server = serve(self._handler, "127.0.0.1", self.port)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.server.shutdown()

    def _handler(self, ws: ServerConnection) -> None:
        try:
            first = json.loads(ws.recv())
            self.received.append(first)
            if (
                first.get("cmd") != "auth"
                or first.get("token") != self.token
                or first.get("protocol") != 2
            ):
                ws.close(code=1008, reason="bad auth")
                return
            ws.send(
                json.dumps(
                    {"id": first["id"], "ok": True, "protocol": self.reply_protocol}
                )
            )
            while True:
                msg = json.loads(ws.recv())
                self.received.append(msg)
                rid = msg.get("id")
                if self.wrong_id_once:
                    rid = rid + 999
                    self.wrong_id_once = False
                cmd = msg.get("cmd")
                out: dict[str, Any]
                if cmd == "ping":
                    out = {"ok": True}
                elif cmd == "scene_tree":
                    out = {"tree": TREE}
                elif cmd == "capture":
                    out = {"frame": self.capture}
                elif cmd == "get_property":
                    out = {"value": "STATUS: IDLE"}
                elif cmd in ("set_property", "restart_scene"):
                    out = {"ok": True}
                elif cmd == "inject":
                    out = (
                        {"ok": True, "tier": "a3"}
                        if self.inject_ok
                        else {
                            "ok": False,
                            "tier": "a3",
                            "error": "no bound XRController3D",
                        }
                    )
                else:
                    out = {"error": f"unknown cmd {cmd}"}
                out["id"] = rid
                ws.send(json.dumps(out))
        except ConnectionClosed:
            return


@pytest.fixture
def engine() -> Any:
    e = FakeEngine()
    yield e
    e.stop()


def _driver(engine: FakeEngine, **kw: Any) -> GodotDriver:
    d = GodotDriver(port=engine.port, timeout_s=2.0, **kw)
    d.connect(token=TOKEN)
    return d


def _capture_reply(path: Path, tier: str = "t3", **over: Any) -> dict[str, Any]:
    data = path.read_bytes()
    reply = {
        "path": str(path),
        "tier": tier,
        "sha256": hashlib.sha256(data).hexdigest(),
        "width": 64,
        "height": 36,
        "frame_id": 1,
    }
    reply.update(over)
    return reply


# -- auth and framing ------------------------------------------------------


def test_auth_frame_carries_token_and_protocol(engine: FakeEngine) -> None:
    d = _driver(engine)
    assert engine.received[0]["cmd"] == "auth"
    assert engine.received[0]["token"] == TOKEN
    assert engine.received[0]["protocol"] == 2
    assert d.get_property("/root/Main/StatusLabel", "text") == "STATUS: IDLE"
    d.close()


def test_bad_token_raises_auth_error() -> None:
    e = FakeEngine()
    try:
        with pytest.raises(AuthError):
            GodotDriver(port=e.port, timeout_s=2.0).connect(token="b" * 64)
    finally:
        e.stop()


def test_protocol_mismatch_raises_auth_error() -> None:
    e = FakeEngine(reply_protocol=3)
    try:
        with pytest.raises(AuthError, match="protocol mismatch"):
            GodotDriver(port=e.port, timeout_s=2.0).connect(token=TOKEN)
    finally:
        e.stop()


def test_reply_id_mismatch_is_protocol_error() -> None:
    e = FakeEngine(wrong_id_once=True)
    try:
        d = _driver(e)
        with pytest.raises(ProtocolError, match="id mismatch"):
            d.scene_tree()
    finally:
        e.stop()


def test_token_file_validation(tmp_path: Path) -> None:
    good = tmp_path / "openxr_operator.token"
    good.write_text(TOKEN + "\n")
    assert read_token(good) == TOKEN
    bad = tmp_path / "bad.token"
    bad.write_text("not-a-token")
    with pytest.raises(AuthError):
        read_token(bad)


def test_unconnected_driver_raises() -> None:
    with pytest.raises(DriverError, match="not connected"):
        GodotDriver().scene_tree()


# -- TC-SEC-004: capability gate before dispatch ---------------------------


def test_tc_sec_004_mutation_outside_capabilities_never_sent(
    engine: FakeEngine, caplog: pytest.LogCaptureFixture
) -> None:
    d = _driver(engine)  # capabilities defaults to empty
    with caplog.at_level(logging.WARNING, logger="openxr_operator.driver"):
        with pytest.raises(ActionRejected):
            d.set_property("/root/Main/StatusLabel", "text", "PWNED")
        with pytest.raises(ActionRejected):
            d.restart_scene()
        with pytest.raises(ActionRejected):
            d.move_controller("right", (0.0, 1.0, -0.4), (0.0, 0.0, 0.0, 1.0))
    assert [m["cmd"] for m in engine.received] == ["auth"]  # nothing on the wire
    assert "capability rejection" in caplog.text


def test_granted_mutation_dispatches(engine: FakeEngine) -> None:
    d = _driver(engine, capabilities=frozenset({"set_property"}))
    d.set_property("/root/Main/StatusLabel", "text", "STATUS: RED")
    assert engine.received[-1]["cmd"] == "set_property"
    assert engine.received[-1]["value"] == "STATUS: RED"


# -- observation -----------------------------------------------------------


def test_scene_tree_parses_into_contract_nodes(engine: FakeEngine) -> None:
    d = _driver(engine)
    tree = d.scene_tree()
    main = tree.children[0]
    label = main.children[0]
    assert tree.cls == "Node"
    assert label.text == "STATUS: IDLE"
    origin = main.children[1].children[0]
    assert origin.groups == ("xr_origin",)
    assert len(origin.children) == 3


def test_capture_verified_tier_and_hash(engine: FakeEngine, tmp_path: Path) -> None:
    from PIL import Image

    png = tmp_path / "frame.png"
    Image.new("RGB", (64, 36), (10, 20, 30)).save(png)
    engine.capture = _capture_reply(png)
    d = _driver(engine, capture_tier="t3")
    frame = d.capture()
    assert frame.tier == "t3"
    assert frame.image == png.read_bytes()
    assert frame.sha256 == hashlib.sha256(frame.image).hexdigest()
    assert (frame.width, frame.height) == (64, 36)


def test_capture_tier_mismatch_rejected(engine: FakeEngine, tmp_path: Path) -> None:
    from PIL import Image

    png = tmp_path / "frame.png"
    Image.new("RGB", (64, 36)).save(png)
    engine.capture = _capture_reply(png, tier="t3")
    d = _driver(engine, capture_tier="t2")
    with pytest.raises(CaptureVerificationError, match="tier mismatch"):
        d.capture()


def test_capture_hash_mismatch_rejected(engine: FakeEngine, tmp_path: Path) -> None:
    from PIL import Image

    png = tmp_path / "frame.png"
    Image.new("RGB", (64, 36)).save(png)
    engine.capture = _capture_reply(png, sha256="0" * 64)
    d = _driver(engine, capture_tier="t3")
    with pytest.raises(CaptureVerificationError, match="sha256 mismatch"):
        d.capture()


def test_capture_black_frame_is_error_not_artifact(
    engine: FakeEngine, tmp_path: Path
) -> None:
    from PIL import Image

    png = tmp_path / "frame.png"
    Image.new("RGB", (64, 36)).save(png)
    engine.capture = _capture_reply(png, black=True)
    d = _driver(engine, capture_tier="t3")
    with pytest.raises(CaptureVerificationError, match="black frame"):
        d.capture()


# -- F-012 propagation -----------------------------------------------------


def test_bogus_injection_raises_named_error_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    e = FakeEngine(inject_ok=False)
    try:
        d = _driver(e, capabilities=frozenset({"move_controller"}))
        with (
            caplog.at_level(logging.WARNING, logger="openxr_operator.driver"),
            pytest.raises(TrackerBindError),
        ):
            d.move_controller("right", (0.0, 1.0, -0.4), (0.0, 0.0, 0.0, 1.0))
        assert "injection rejected" in caplog.text
    finally:
        e.stop()


# -- integration -----------------------------------------------------------


@pytest.mark.skip(
    reason="real addon server lands with W2-01-addon-server; QA roundtrip "
    "(W2-02-qa-contract-roundtrip) replays this pair for real — marked, not "
    "silently skipped, per the driver card"
)
def test_integration_real_addon_server() -> None:
    raise AssertionError("replaced by the QA contract-roundtrip replay")
