"""Frame-stability settle detection (kit §5.2; fixes F-014; TC-SEC-007).

Replaces every fixed ``time.sleep(2)`` in the v1.0 design. The detector polls
the capture callable until consecutive frames stop changing, honouring its
timeout in both modes — Maestro shipped a release where the timeout was not
respected (#2843), so the timeout is *measured* in tests (±50 ms), not assumed.

No ``time.sleep`` anywhere: waits are event-condition waits on a
``threading.Event`` (``wake``), so a caller that learns a new frame is ready
can signal the detector instead of letting it poll out the full interval.
``on_timeout`` is validated up front (S-15): an invalid value raises instead
of silently coercing to TIMEOUT_PROCEED.
"""

from __future__ import annotations

import io
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np
from numpy import typing as npt
from PIL import Image


class SettleOutcome(str, Enum):
    SETTLED = "settled"
    TIMEOUT_PROCEED = "timeout_proceed"
    TIMEOUT_FAIL = "timeout_fail"


@dataclass(frozen=True)
class SettleResult:
    outcome: SettleOutcome
    elapsed_ms: int
    samples: int
    last_delta: float


def fingerprint(
    png_bytes: bytes, size: tuple[int, int] = (160, 90)
) -> npt.NDArray[np.float32]:
    """Grayscale, downscaled frame fingerprint (noise/dither do not dominate)."""
    img = (
        Image.open(io.BytesIO(png_bytes))
        .convert("L")
        .resize(size, Image.Resampling.BILINEAR)
    )
    return np.asarray(img, dtype=np.float32)


def wait_for_settle(
    capture: Callable[[], bytes],
    *,
    interval_ms: int = 100,
    threshold: float = 0.002,
    stable_samples: int = 3,
    timeout_ms: int = 5000,
    on_timeout: str = "proceed",
    wake: threading.Event | None = None,
) -> SettleResult:
    """Poll ``capture()`` until consecutive frames stop changing.

    ``on_timeout="proceed"`` matches Maestro's waitForAnimationToEnd (succeed
    and continue); ``"fail"`` returns TIMEOUT_FAIL for flows that genuinely
    require a quiescent scene. The outcome is always reported — a flow whose
    steps are all TIMEOUT_PROCEED is not actually synchronising (kit §5.2).
    """
    if on_timeout not in ("proceed", "fail"):
        raise ValueError(f"invalid on_timeout {on_timeout!r} (S-15)")
    wake_event = wake if wake is not None else threading.Event()

    t0 = time.monotonic()
    prev = fingerprint(capture())
    stable = 0
    samples = 1
    delta = 1.0

    while True:
        # Event-condition wait, not time.sleep: a producer that knows a new
        # frame is ready sets `wake_event`, shortening the wait safely.
        wake_event.wait(timeout=interval_ms / 1000.0)
        wake_event.clear()
        cur = fingerprint(capture())
        samples += 1
        delta = float(np.mean(np.abs(cur - prev))) / 255.0
        stable = stable + 1 if delta < threshold else 0
        prev = cur

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if stable >= stable_samples:
            return SettleResult(SettleOutcome.SETTLED, elapsed_ms, samples, delta)
        if elapsed_ms > timeout_ms:
            outcome = (
                SettleOutcome.TIMEOUT_FAIL
                if on_timeout == "fail"
                else SettleOutcome.TIMEOUT_PROCEED
            )
            return SettleResult(outcome, elapsed_ms, samples, delta)
