"""Settle detector tests (TC-SEC-007; Maestro #2843; S-15).

The timeout is measured, not assumed: both on_timeout modes must return
within ±50 ms of the configured deadline while frames keep changing.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from PIL import Image

from openxr_operator.settle import SettleOutcome, wait_for_settle


def _png(value: int) -> bytes:
    buf = io.BytesIO()
    Image.new("L", (64, 36), value).save(buf, format="PNG")
    return buf.getvalue()


def _alternating() -> Iterator[bytes]:
    while True:
        yield _png(0)
        yield _png(255)


def test_settles_on_static_frames() -> None:
    result = wait_for_settle(lambda: _png(42), timeout_ms=2000, interval_ms=20)
    assert result.outcome is SettleOutcome.SETTLED
    assert result.samples >= 4
    assert result.elapsed_ms < 2000


@pytest.mark.parametrize(
    ("on_timeout", "expected"),
    [
        ("proceed", SettleOutcome.TIMEOUT_PROCEED),
        ("fail", SettleOutcome.TIMEOUT_FAIL),
    ],
)
def test_tc_sec_007_timeout_honoured_within_50ms(
    on_timeout: str, expected: SettleOutcome
) -> None:
    frames = _alternating()
    result = wait_for_settle(
        lambda: next(frames), timeout_ms=300, interval_ms=50, on_timeout=on_timeout
    )
    assert result.outcome is expected
    assert abs(result.elapsed_ms - 300) <= 50, (
        f"timeout not honoured: {result.elapsed_ms} ms vs 300 ms deadline"
    )


def test_invalid_on_timeout_raises_s15() -> None:
    with pytest.raises(ValueError, match="on_timeout"):
        wait_for_settle(lambda: _png(0), on_timeout="whatever")  # type: ignore[arg-type]
