"""Driver protocol (FROZEN contract — orchestrator-owned).

The seam that makes capture tiers (T1/T2/T3) and injection tiers (A1/A2/A3)
interchangeable. Everything above this protocol is engine-agnostic.
Frame carries the tier actually used, so a report can never claim a
fidelity it did not have.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

CaptureTier = Literal["t1", "t2", "t3"]
InjectTier = Literal["a1", "a2", "a3"]


@dataclass(frozen=True)
class Frame:
    image: bytes
    tier: CaptureTier
    frame_id: int
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class TreeNode:
    name: str
    cls: str
    path: str
    visible: bool
    groups: tuple[str, ...]
    text: str | None
    children: tuple["TreeNode", ...]
    truncated_children: int


class Driver(Protocol):
    def launch(self, scene: str, clean: bool = False) -> None: ...
    def shutdown(self) -> None: ...
    def capture(self, tier: CaptureTier | None = None) -> Frame: ...
    def scene_tree(
        self, root: str = "/root", depth: int = 6, include: list[str] | None = None
    ) -> TreeNode: ...
    def get_property(self, path: str, prop: str) -> Any: ...
    def set_property(self, path: str, prop: str, value: Any) -> None: ...
    def move_controller(
        self,
        hand: Literal["left", "right"],
        position: tuple[float, float, float],
        rotation: tuple[float, float, float, float],
        tier: InjectTier | None = None,
    ) -> None: ...
    def press(
        self,
        hand: Literal["left", "right"],
        action: str,
        value: float,
        tier: InjectTier | None = None,
    ) -> None: ...
    def restart_scene(self) -> None: ...

    @property
    def available_capture_tiers(self) -> list[CaptureTier]: ...
    @property
    def available_inject_tiers(self) -> list[InjectTier]: ...
