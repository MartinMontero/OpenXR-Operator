"""Filesystem containment for model-supplied paths (kit §6.4; fixes F-003).

Every path the runner touches — frames to disk, artifacts, logs, and
model-proposed file writes — must resolve through :func:`safe_target` /
:func:`safe_write` before it reaches the filesystem. The resolution root is
the launched project's directory, captured once at flow start by the caller
and passed in as ``project_root``; the guard never accepts a root from model
output.

Two ``pathlib`` traps make a naive join unsafe (F-003): an absolute
right-hand operand silently discards the base (``Path("/proj") /
"/etc/passwd"``), and ``..`` segments are not normalised by the join. Both
are rejected up front. The load-bearing check is resolve-then-contain: the
candidate is fully resolved (symlinks and junctions followed) and must remain
under the resolved root. A suffix allowlist and a size cap bound what a
contained write may do.

Residual TOCTOU window (S-04 — documented, accepted)
----------------------------------------------------
Kit §6.4 carried a final ``target.is_symlink()`` rejection. It was removed:

* It was dead code. After ``Path.resolve()``, the returned leaf is never a
  symlink — resolution has already followed every link — so the check could
  not fire. Any link present at check time is already caught by the
  resolve-then-contain comparison.
* It was not load-bearing. A link created *after* the check defeats the
  check just as surely as it defeats the containment comparison: the gap
  between check and use cannot be closed by re-statting the path. The check
  bought a false sense of finality, not protection.

The residual window: between resolve-then-contain here and the caller's
eventual ``open()``, an attacker could swap a directory component inside the
project root for a symlink or junction pointing outside, and the write would
follow it. That requires a second process with write access inside the
project root racing a single write — code already inside the trust boundary.
What still protects the path: the OS-level filesystem jail (kit §3.4, D-05)
confines the process to the project directory; mutating writes additionally
pass the diff-then-approve gate (kit §3.4); and every rejection below is
logged before it raises, so the attempt is visible in the run record.

Every rejection raises :class:`PathRejected` *and* logs a WARNING on the
``openxr_operator.fsguard`` logger before raising (W2 exit gate; TC-SEC-003).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NoReturn

ALLOWED_SUFFIXES = frozenset({".gd", ".tres", ".tscn", ".json", ".cfg", ".md"})
MAX_BYTES = 256 * 1024

_LOG = logging.getLogger("openxr_operator.fsguard")


class PathRejected(ValueError):
    """A model-supplied or flow-supplied path failed containment."""


def _reject(reason: str, relative_path: str, project_root: str | Path) -> NoReturn:
    """Log the rejection, then raise. Log-then-raise is the contract."""
    _LOG.warning(
        "fsguard rejected path: reason=%s attempted=%r project_root=%s",
        reason,
        relative_path,
        project_root,
    )
    raise PathRejected(f"{reason}: {relative_path!r}")


def safe_target(project_root: str | Path, relative_path: str) -> Path:
    """Resolve ``relative_path`` under ``project_root`` or raise.

    Handles the two pathlib traps: an absolute right-hand operand discards
    the base entirely, and ``..`` segments are not normalised by the join.
    Returns the fully resolved target; the caller still owes the actual
    write (see the TOCTOU note in the module docstring).

    Raises:
        PathRejected: the path is empty/padded, absolute, contains ``..``,
            resolves outside ``project_root`` (including via a symlink or
            junction present at check time), or has a disallowed suffix.
        FileNotFoundError: ``project_root`` itself does not exist — a caller
            bug, not a model attack, so it is not converted to PathRejected.
    """
    if not relative_path or relative_path.strip() != relative_path:
        _reject("empty or padded path", relative_path, project_root)

    candidate = Path(relative_path)
    if candidate.is_absolute() or candidate.drive or candidate.root:
        _reject("absolute path", relative_path, project_root)
    if ".." in candidate.parts:
        _reject("parent traversal", relative_path, project_root)

    base = Path(project_root).resolve(strict=True)
    target = (base / candidate).resolve()

    if not target.is_relative_to(base):
        _reject("escapes project root", relative_path, project_root)
    suffix = target.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        _reject(
            f"suffix not allowed ({suffix or '<none>'})", relative_path, project_root
        )
    return target


def safe_write(project_root: str | Path, relative_path: str, content: str) -> Path:
    """Write ``content`` to a contained path or raise.

    The size cap is checked before any containment work or I/O, and nothing
    is written — not even parent directories — unless the target passes
    :func:`safe_target`.
    """
    data = content.encode("utf-8")
    if len(data) > MAX_BYTES:
        _reject(
            f"content too large ({len(data)} bytes > {MAX_BYTES})",
            relative_path,
            project_root,
        )
    target = safe_target(project_root, relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target
