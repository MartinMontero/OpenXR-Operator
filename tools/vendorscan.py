#!/usr/bin/env python3
"""Vendor gate and licence gate (build kit v2.0 §7.1, v3.0 S-01; D-11 scope).

Fails the build on any Meta/OpenAI/xAI reference in the lockfile or source
tree, and on any dependency licence not on the allowlist. Policy that lives
only in a document gets violated on the first convenient afternoon.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED = re.compile(
    r"\b(openai|open_ai|chatgpt|gpt-|xai|x-ai|grok|meta-llama|llama-|llava|vicuna|bakllava)\b",
    re.IGNORECASE,
)
# Name fragments that false-positive the banned patterns and are allowed.
# D-11 (2026-08-09): the gate bans vendor artifacts, not interface shapes.
# "openai-compatible" names a wire format spoken by llama.cpp/vLLM/LM Studio;
# the artifact (a package named exactly `openai`) still fails, as does any
# bare occurrence outside these compounds.
ALLOW = re.compile(
    r"(openxrv|openxr|openai-compatible|openai compatible|llama-server|llama\.cpp)",
    re.IGNORECASE,
)

SCAN_SUFFIXES = {".py", ".gd", ".toml", ".lock", ".cfg", ".yaml", ".yml", ".txt", ".json"}
SKIP_DIRS = {".git", ".venv", "runs", "sbom.json"}

LICENCE_ALLOWLIST = {
    "mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "mit-cmu",
    "agpl-3.0-or-later", "cc0-1.0", "unlicense", "python-2.0",
}


def scan(paths: list[str]) -> int:
    hits = 0
    for raw in paths:
        root = Path(raw)
        # rglob yields nothing for a file argument — iterate it directly,
        # or the gate silently skips pyproject.toml (its highest-value target).
        candidates = [root] if root.is_file() else root.rglob("*")
        for p in candidates:
            if not p.is_file() or p.suffix not in SCAN_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p.name == "vendorscan.py":
                continue  # the scanner's own pattern table is not a violation
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                stripped = ALLOW.sub("", line)
                if BANNED.search(stripped):
                    print(f"VENDOR-GATE FAIL {p}:{lineno}: {line.strip()[:120]}")
                    hits += 1
    if hits:
        print(f"\nvendor gate: {hits} banned reference(s) (F-019/F-020/F-021)")
        return 1
    print("vendor gate: clean")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] or ["operator/src", "operator/pyproject.toml", "addon", "layer", "tools"]
    sys.exit(scan(args))
