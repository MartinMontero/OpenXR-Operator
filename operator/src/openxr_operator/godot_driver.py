"""Operator-side client of wire protocol v2, behind the frozen Driver contract.

Card: swarm/tasks/W2-02-operator-driver.md (F-004, F-017 companion, F-012
propagation; audit TC-SEC-004; S-06). docs/contracts/wire-protocol.md is the
authority; this module never edits the contract.

Security behavior:
- Token-first auth with the protocol version in the auth frame. Any failure
  (close 1008, error reply, version mismatch) raises AuthError; no command is
  ever dispatched before a successful auth.
- Every request carries a correlation id; a mismatched or unsolicited reply
  id is a ProtocolError, never a guess (F-017 companion).
- Every mutating command passes schema.validate_action against the flow's
  capabilities BEFORE anything reaches the wire (TC-SEC-004 / F-004). A
  rejection is logged and raised locally; the fake-server tests assert that
  no frame was sent.
- Capture replies are verified before acceptance: declared tier must match,
  the sha256 must match the bytes on disk, and an engine-reported black
  frame is an error, never an artifact (TC-SEC-005 propagation).
- A bogus-tracker failure from the engine propagates as TrackerBindError
  and is logged (F-012 propagation; W2 exit gate, operator side).

Token sourcing: read_token() takes an operator-supplied configuration path.
fsguard deliberately does NOT apply here — it contains model-supplied paths;
the token path is trusted operator configuration, never model output.

S-06 (num_ctx budget): measured against the demo scene tree fixture with the
qwen2.5 tokenizer; see S06_MEASUREMENT below for the executed numbers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from .driver import CaptureTier, Driver, Frame, InjectTier, TreeNode
from .schema import ActionRejected, validate_action

logger = logging.getLogger("openxr_operator.driver")

PROTOCOL_VERSION = 2
MAX_FRAME_BYTES = 1_048_576
_CAPTURE_TIERS = ("t1", "t2", "t3")

# Executed 2026-10-30 (Qwen/Qwen2.5-7B tokenizer.json via hf-mirror;
# tokenizers 0.23.3) against the demo scene tree fixture, D-17 compact render:
#   prompt (task + delimiters + compact tree): 336 tokens; system: 12;
#   one 768x432 frame: ~423 image tokens (28x28 patches) => 771 total.
#   num_ctx 8192 leaves 7,421 tokens (~91%) headroom on the demo scene.
#   Tree alone: pretty-printed 425 vs compact 263 tokens (-38%).
#   A full 1280x720 frame costs ~1,175 tokens: downscale for act(), keep
#   full-res only in artifacts. Re-measure on real XR-scale trees at W4.
S06_MEASUREMENT = (
    "771 tokens total (336 prompt + 12 system + ~423 frame) vs 8192 num_ctx; "
    "7,421 tokens headroom on the demo tree, measured 2026-10-30"
)


class DriverError(RuntimeError):
    """Any driver-level failure (transport, protocol, verification)."""


class ProtocolError(DriverError):
    """Wire-protocol violation, including reply-id mismatch (F-017)."""


class AuthError(DriverError):
    """Authentication or protocol-version negotiation failed."""


class CaptureVerificationError(DriverError):
    """Capture artifact failed tier/hash/black-frame verification."""


class TrackerBindError(DriverError):
    """Injection bound no XRController3D (F-012): a hard error, never a no-op."""


def read_token(path: Path) -> str:
    """Read the engine token from an operator-supplied path (see module docs)."""
    token = path.read_text(encoding="utf-8").strip()
    if len(token) != 64 or any(c not in "0123456789abcdefABCDEF" for c in token):
        raise AuthError(f"token file {path} does not contain 64 hex chars")
    return token


def _tree_from_dict(data: dict[str, Any]) -> TreeNode:
    children = tuple(
        _tree_from_dict(c) for c in data.get("children", []) if isinstance(c, dict)
    )
    return TreeNode(
        name=str(data.get("name", "")),
        cls=str(data.get("class", "")),
        path=str(data.get("path", "")),
        visible=bool(data.get("visible", True)),
        groups=tuple(str(g) for g in data.get("groups", [])),
        text=(str(data["text"]) if "text" in data else None),
        children=children,
        truncated_children=int(data.get("children_truncated", 0)),
    )


class GodotDriver(Driver):
    """Synchronous WebSocket client for the addon's authenticated server."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 9099,
        capabilities: frozenset[str] = frozenset(),
        capture_tier: CaptureTier | None = None,
        timeout_s: float = 10.0,
        godot_binary: str | None = None,
        project: str | None = None,
    ) -> None:
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise DriverError(f"engine channel is loopback-only, got {host!r}")
        self._url = f"ws://{host}:{port}"
        self._capabilities = capabilities
        self._capture_tier = capture_tier
        self._timeout_s = timeout_s
        self._godot_binary = godot_binary
        self._project = project
        self._ws: ClientConnection | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._seq = 0
        self._frames = 0

    # -- transport ---------------------------------------------------------

    def connect(self, *, token: str) -> None:
        """Open the channel and authenticate. Nothing dispatches pre-auth."""
        self._ws = connect(
            self._url,
            open_timeout=self._timeout_s,
            close_timeout=1,
            max_size=MAX_FRAME_BYTES,
        )
        try:
            reply = self._request("auth", token=token, protocol=PROTOCOL_VERSION)
        except DriverError as exc:
            self.close()
            raise AuthError(f"authentication failed: {exc}") from exc
        if not reply.get("ok"):
            self.close()
            raise AuthError(f"authentication rejected: {reply.get('error')}")
        if reply.get("protocol") != PROTOCOL_VERSION:
            self.close()
            raise AuthError(
                f"protocol mismatch: server {reply.get('protocol')!r}, "
                f"client {PROTOCOL_VERSION}"
            )

    def close(self) -> None:
        if self._ws is not None:
            self._ws.close()
            self._ws = None

    def _conn(self) -> ClientConnection:
        if self._ws is None:
            raise DriverError("not connected; call connect() first")
        return self._ws

    def _request(self, cmd: str, **params: Any) -> dict[str, Any]:
        ws = self._conn()
        self._seq += 1
        rid = self._seq
        ws.send(json.dumps({"cmd": cmd, "id": rid, **params}))
        deadline = time.monotonic() + self._timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProtocolError(f"timeout waiting for reply to {cmd!r} id={rid}")
            try:
                raw = ws.recv(timeout=remaining)
            except TimeoutError as exc:
                raise ProtocolError(
                    f"timeout waiting for reply to {cmd!r} id={rid}"
                ) from exc
            except ConnectionClosed as exc:
                raise DriverError(
                    f"engine closed the channel during {cmd!r}: "
                    f"{exc.rcvd.code if exc.rcvd else 'no close frame'}"
                ) from exc
            if isinstance(raw, bytes):
                raise ProtocolError("binary frame on a JSON-only channel")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ProtocolError("reply is not a JSON object")
            if data.get("id") != rid:
                raise ProtocolError(
                    f"reply id mismatch: sent {rid}, got {data.get('id')!r} (F-017)"
                )
            return data

    def _gate(self, action: dict[str, Any]) -> None:
        """Capability check BEFORE dispatch (TC-SEC-004). Logged on rejection."""
        try:
            validate_action(action, self._capabilities)
        except ActionRejected:
            logger.warning(
                "driver capability rejection before dispatch: action=%s path=%s",
                action.get("action"),
                action.get("path"),
            )
            raise

    # -- Driver contract ---------------------------------------------------

    def launch(self, scene: str, clean: bool = False) -> None:
        """Start the engine process (only when binary/project are configured).

        ``clean`` is advisory: no destructive cleanup is ever performed here;
        state reset semantics belong to the W3 flow runner.
        """
        if self._godot_binary is None or self._project is None:
            raise DriverError("launch requires godot_binary and project configured")
        if clean:
            logger.info("launch(clean=True): no destructive cleanup performed")
        self._proc = subprocess.Popen(
            [self._godot_binary, "--path", self._project, scene]
        )

    def shutdown(self) -> None:
        self.close()
        if self._proc is not None:
            self._proc.terminate()
            self._proc = None

    def capture(self, tier: CaptureTier | None = None) -> Frame:
        requested = tier or self._capture_tier
        params: dict[str, Any] = {"label": f"frame-{self._frames + 1:04d}"}
        if requested is not None:
            params["tier"] = requested
        reply = self._request("capture", **params)
        frame = reply.get("frame")
        if not isinstance(frame, dict):
            raise ProtocolError("capture reply has no frame object")
        return self._verify_frame(frame)

    def _verify_frame(self, frame: dict[str, Any]) -> Frame:
        tier = str(frame.get("tier", ""))
        if tier not in _CAPTURE_TIERS:
            raise CaptureVerificationError(f"unknown capture tier {tier!r}")
        if self._capture_tier is not None and tier != self._capture_tier:
            raise CaptureVerificationError(
                f"tier mismatch: flow declares {self._capture_tier}, "
                f"engine returned {tier}"
            )
        if frame.get("black") is True:
            raise CaptureVerificationError(
                "engine reported a black frame; not an artifact (TC-SEC-005)"
            )
        path = Path(str(frame.get("path", "")))
        try:
            image = path.read_bytes()
        except OSError as exc:
            raise CaptureVerificationError(f"frame not readable: {path}") from exc
        digest = hashlib.sha256(image).hexdigest()
        if digest != str(frame.get("sha256", "")):
            raise CaptureVerificationError(
                f"sha256 mismatch for {path}: engine {frame.get('sha256')!r}, "
                f"on disk {digest!r}"
            )
        self._frames += 1
        return Frame(
            image=image,
            tier=tier,  # type: ignore[arg-type]
            frame_id=int(frame.get("frame_id", self._frames)),
            sha256=digest,
            width=int(frame.get("width", 0)),
            height=int(frame.get("height", 0)),
        )

    def scene_tree(
        self, root: str = "/root", depth: int = 6, include: list[str] | None = None
    ) -> TreeNode:
        params: dict[str, Any] = {"root": root, "depth": depth}
        if include is not None:
            params["include"] = include
        reply = self._request("scene_tree", **params)
        tree = reply.get("tree")
        if not isinstance(tree, dict):
            raise ProtocolError("scene_tree reply has no tree object")
        return _tree_from_dict(tree)

    def get_property(self, path: str, prop: str) -> Any:
        reply = self._request("get_property", path=path, property=prop)
        if "error" in reply:
            raise DriverError(f"get_property failed: {reply['error']}")
        return reply.get("value")

    def set_property(self, path: str, prop: str, value: Any) -> None:
        self._gate(
            {
                "action": "set_property",
                "rationale": "driver set_property",
                "path": path,
                "property": prop,
                "value": value,
            }
        )
        reply = self._request("set_property", path=path, property=prop, value=value)
        if "error" in reply:
            raise DriverError(f"set_property failed: {reply['error']}")

    def move_controller(
        self,
        hand: Literal["left", "right"],
        position: tuple[float, float, float],
        rotation: tuple[float, float, float, float],
        tier: InjectTier | None = None,
    ) -> None:
        self._gate(
            {
                "action": "move_controller",
                "rationale": "driver move_controller",
                "hand": hand,
                "position": list(position),
                "rotation": list(rotation),
            }
        )
        self._inject(
            "move_controller",
            hand=hand,
            position=list(position),
            rotation=list(rotation),
            tier=tier,
        )

    def press(
        self,
        hand: Literal["left", "right"],
        action: str,
        value: float,
        tier: InjectTier | None = None,
    ) -> None:
        self._gate(
            {
                "action": "press",
                "rationale": "driver press",
                "hand": hand,
                "action_name": action,
                "float_value": value,
            }
        )
        self._inject(
            "press", hand=hand, action_name=action, float_value=value, tier=tier
        )

    def _inject(self, op: str, **params: Any) -> None:
        reply = self._request("inject", op=op, **params)
        if not reply.get("ok", False):
            logger.warning("injection rejected by engine: %s", reply.get("error"))
            raise TrackerBindError(
                f"injection bound nothing or was rejected: {reply.get('error')} "
                "(F-012: silent no-op injection is the worst outcome)"
            )

    def restart_scene(self) -> None:
        self._gate({"action": "restart_scene", "rationale": "driver restart_scene"})
        reply = self._request("restart_scene")
        if "error" in reply:
            raise DriverError(f"restart_scene failed: {reply['error']}")

    @property
    def available_capture_tiers(self) -> list[CaptureTier]:
        if self._capture_tier is not None:
            return [self._capture_tier]
        return ["t2", "t3"]  # v1 ships T2/T3 (D-04); T1 is layer-gated

    @property
    def available_inject_tiers(self) -> list[InjectTier]:
        return ["a3"]  # A1/A2 require runtime extension or the API layer
