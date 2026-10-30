"""Append-only, hash-chained audit log (kit §3.7; S-08).

"Append-only" without an integrity mechanism is a claim, not a control. Every
record carries the SHA-256 of the previous record and its own hash, computed
over its canonical JSON plus the previous hash. Editing, deleting, reordering,
or truncating lines breaks the chain and `verify()` reports it. (Deleting
whole lines from the END of a log cannot be detected by any chain alone; an
external anchor is needed, so `head_hash()` exposes the chain head for the
caller to pin.)

Written BEFORE execution: timestamp, flow/step, action and parameters, frame
and tree hashes, capture tier, approval decision and approver, execution
result, and the diff for mutating actions. Secret-shaped values (tokens,
keys, passwords) are redacted at write time — the engine token must never
appear in any log or artifact (P3-12).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

GENESIS = "0" * 64
_SECRET_KEYS = {"token", "secret", "api_key", "apikey", "password", "authorization"}


def redact(value: Any) -> Any:
    """Recursively replace secret-shaped values with [redacted]."""
    if isinstance(value, dict):
        return {
            k: ("[redacted]" if k.lower() in _SECRET_KEYS else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def _hash_record(record: dict[str, Any], prev_hash: str) -> str:
    payload = {k: v for k, v in record.items() if k != "record_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


class AuditLog:
    """Hash-chained JSON Lines writer. One file per durable log."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._prev = GENESIS
        self._seq = 0
        if self._path.exists():
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    last = json.loads(line)
                    self._prev = str(last["record_hash"])
                    self._seq = int(last["seq"])

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        """Chain and append one record. Returns the stored record."""
        self._seq += 1
        stored: dict[str, Any] = {
            "seq": self._seq,
            "timestamp": datetime.now(UTC).isoformat(),
            **redact(record),
            "prev_hash": self._prev,
        }
        stored["record_hash"] = _hash_record(stored, self._prev)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(stored) + "\n")
        self._prev = str(stored["record_hash"])
        return stored


def verify(path: Path) -> bool:
    """Recompute the chain. False on any edit, deletion, reorder, or truncation."""
    if not path.exists():
        return False
    prev = GENESIS
    expected_seq = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return False
        expected_seq += 1
        if record.get("seq") != expected_seq or record.get("prev_hash") != prev:
            return False
        if _hash_record(record, prev) != record.get("record_hash"):
            return False
        prev = str(record["record_hash"])
    return expected_seq > 0


def head_hash(path: Path) -> str:
    """The chain head (last record_hash). Pin it externally to detect
    end-of-file truncation: a shortened log has a different head."""
    last = GENESIS
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = str(json.loads(line)["record_hash"])
    return last
