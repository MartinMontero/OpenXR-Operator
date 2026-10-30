"""TC-SEC-003 (F-003): containment rejections raise AND are logged.

AAA form; deterministic; no filesystem fixtures outside tmp_path. The
symlink-escape case falls back to a directory junction on Windows hosts
without the symlink privilege (same escape vector — Path.resolve() follows
junctions) and skips only if the host permits neither.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

import pytest

from openxr_operator.fsguard import (
    ALLOWED_SUFFIXES,
    MAX_BYTES,
    PathRejected,
    safe_target,
    safe_write,
)

GUARD_LOGGER = "openxr_operator.fsguard"


def _project(tmp_path: Path) -> Path:
    # Arrange: a project root with one legitimate file.
    root = tmp_path / "project"
    root.mkdir()
    (root / "ok.gd").write_text("extends Node\n")
    return root


def _assert_logged(caplog: pytest.LogCaptureFixture, *fragments: str) -> None:
    records = [
        r
        for r in caplog.records
        if r.name == GUARD_LOGGER and r.levelno >= logging.WARNING
    ]
    assert records, "rejection was raised but not logged"
    assert any(
        "fsguard rejected" in r.getMessage()
        and all(f in r.getMessage() for f in fragments)
        for r in records
    ), f"no log record contained {fragments!r}: {[r.getMessage() for r in records]!r}"


def _make_outward_link(root: Path, outside: Path, name: str = "link") -> Path:
    """Create root/name -> outside as a symlink, or a junction on Windows."""
    link = root / name
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not link.is_dir():
            pytest.skip("host allows neither symlinks nor directory junctions")
    return link


# --- TC-SEC-003: the four mandatory rejection cases ---------------------------


def test_tc_sec_003_absolute_path_rejected_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange
    root = _project(tmp_path)
    absolute = str(tmp_path / "evil.gd")  # absolute on every platform
    # Act / Assert: raise ...
    with (
        caplog.at_level(logging.WARNING, logger=GUARD_LOGGER),
        pytest.raises(PathRejected, match="absolute path"),
    ):
        safe_target(root, absolute)
    # ... and log.
    _assert_logged(caplog, "absolute path", repr(absolute))


def test_tc_sec_003_parent_traversal_rejected_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange
    root = _project(tmp_path)
    traversal = os.path.join("..", "evil.gd")
    # Act / Assert
    with (
        caplog.at_level(logging.WARNING, logger=GUARD_LOGGER),
        pytest.raises(PathRejected, match="parent traversal"),
    ):
        safe_write(root, traversal, "extends Node\n")
    _assert_logged(caplog, "parent traversal")
    assert not (tmp_path / "evil.gd").exists()


@pytest.mark.skipif(os.name != "nt", reason="backslash traversal is Windows-only")
def test_tc_sec_003_backslash_traversal_rejected_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange
    root = _project(tmp_path)
    # Act / Assert
    with (
        caplog.at_level(logging.WARNING, logger=GUARD_LOGGER),
        pytest.raises(PathRejected, match="parent traversal"),
    ):
        safe_target(root, "..\\evil.gd")
    _assert_logged(caplog, "parent traversal")


def test_tc_sec_003_symlink_escape_rejected_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange: root/link -> outside; a write through the link would land outside.
    root = _project(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    _make_outward_link(root, outside)
    # Act / Assert
    with (
        caplog.at_level(logging.WARNING, logger=GUARD_LOGGER),
        pytest.raises(PathRejected, match="escapes project root"),
    ):
        safe_write(root, os.path.join("link", "evil.gd"), "extends Node\n")
    _assert_logged(caplog, "escapes project root")
    assert not (outside / "evil.gd").exists()


def test_tc_sec_003_oversize_content_rejected_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange
    root = _project(tmp_path)
    oversize = "x" * (MAX_BYTES + 1)
    # Act / Assert
    with (
        caplog.at_level(logging.WARNING, logger=GUARD_LOGGER),
        pytest.raises(PathRejected, match="content too large"),
    ):
        safe_write(root, "big.gd", oversize)
    _assert_logged(caplog, "content too large")
    assert not (root / "big.gd").exists()


# --- Kit §6.4 behaviour beyond TC-SEC-003 -------------------------------------


def test_valid_relative_path_resolves_inside_root(tmp_path: Path) -> None:
    # Arrange
    root = _project(tmp_path)
    # Act
    target = safe_target(root, "scripts/player.gd")
    # Assert
    assert target.is_relative_to(root.resolve())
    assert target == root.resolve() / "scripts" / "player.gd"


def test_safe_write_creates_parents_and_writes_bytes(tmp_path: Path) -> None:
    # Arrange
    root = _project(tmp_path)
    content = "extends Node\n# héllo\n"
    # Act
    written = safe_write(root, "scripts/player.gd", content)
    # Assert
    assert written.read_bytes() == content.encode("utf-8")


@pytest.mark.parametrize("allowed", sorted(ALLOWED_SUFFIXES))
def test_every_allowed_suffix_accepted(tmp_path: Path, allowed: str) -> None:
    # Arrange
    root = _project(tmp_path)
    # Act / Assert: no raise
    assert safe_target(root, f"file{allowed}").suffix == allowed


def test_disallowed_suffix_rejected_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange
    root = _project(tmp_path)
    # Act / Assert
    with (
        caplog.at_level(logging.WARNING, logger=GUARD_LOGGER),
        pytest.raises(PathRejected, match="suffix not allowed"),
    ):
        safe_target(root, "evil.exe")
    _assert_logged(caplog, "suffix not allowed")


def test_suffixless_path_rejected_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange
    root = _project(tmp_path)
    # Act / Assert
    with (
        caplog.at_level(logging.WARNING, logger=GUARD_LOGGER),
        pytest.raises(PathRejected, match="suffix not allowed"),
    ):
        safe_target(root, "Makefile")
    _assert_logged(caplog, "suffix not allowed")


@pytest.mark.parametrize("bad", ["", "   ", " x.gd", "x.gd "])
def test_empty_or_padded_path_rejected_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, bad: str
) -> None:
    # Arrange
    root = _project(tmp_path)
    # Act / Assert
    with (
        caplog.at_level(logging.WARNING, logger=GUARD_LOGGER),
        pytest.raises(PathRejected, match="empty or padded path"),
    ):
        safe_target(root, bad)
    _assert_logged(caplog, "empty or padded path")


def test_missing_project_root_is_caller_error_not_path_rejected(tmp_path: Path) -> None:
    # Arrange
    missing = tmp_path / "no-such-project"
    # Act / Assert
    with pytest.raises(FileNotFoundError):
        safe_target(missing, "ok.gd")


def test_contained_symlink_within_root_is_accepted(tmp_path: Path) -> None:
    # Arrange: a link whose target stays inside the root resolves inside and passes.
    root = _project(tmp_path)
    real_dir = root / "real"
    real_dir.mkdir()
    try:
        _make_outward_link(root, real_dir, name="inner")  # root/inner -> root/real
    except OSError:
        pytest.skip("host allows neither symlinks nor directory junctions")
    # Act / Assert
    target = safe_target(root, os.path.join("inner", "ok.gd"))
    assert target == real_dir.resolve() / "ok.gd"
