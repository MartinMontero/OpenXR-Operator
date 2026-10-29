"""TC-SEC-010 / P1-01: the vendor gate must reach the lockfile, both ways.

Same standard as the W0 dry-run: executed, in both directions. The fixture
is a copy of the real lockfile in a tmp dir; the real one is never touched.
This is also the W1 exit-gate demonstration for M0 (vendor gate fails when
a banned package enters the lockfile, passes when absent).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCANNER = REPO_ROOT / "tools" / "vendorscan.py"
REAL_LOCK = REPO_ROOT / "operator" / "uv.lock"

BANNED_STANZA = (
    '\n[[package]]\nname = "openai"\nversion = "1.0.0"\n'  # vendorscan:gate-table
)


def _run(*paths: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), *paths],
        capture_output=True,
        check=False,
        text=True,
        cwd=REPO_ROOT,
    )


def test_vendor_gate_fails_on_banned_package_in_lockfile(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    shutil.copy(REAL_LOCK, lock)
    with lock.open("a", encoding="utf-8") as f:
        f.write(BANNED_STANZA)
    result = _run(str(lock))
    assert result.returncode == 1, result.stdout
    assert "VENDOR-GATE FAIL" in result.stdout


def test_vendor_gate_passes_on_pristine_lockfile(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    shutil.copy(REAL_LOCK, lock)
    result = _run(str(lock))
    assert result.returncode == 0, result.stdout
