"""Selector grammar and resolution (kit §5.3; flow contract).

Selectors resolve against the normalised node tree (the frozen TreeNode
contract). Implemented: attribute selectors (name, class, path, text, group,
visible, index) and structural relational operators (child_of, contains).

Screen-space relational operators (below, above, left_of, right_of, near)
require projected bounds, which the v2 wire tree does not carry. They raise
UnsupportedSelector loudly instead of guessing — a selector that silently
resolves to the wrong node is how tests become non-deterministic.

Resolution rules (contract): zero matches is an error unless `optional: true`
(then None); multiple matches without an `index` is an error; every
resolution is logged with the candidate set.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .driver import TreeNode

logger = logging.getLogger("openxr_operator.selectors")

_SCREEN_SPACE_OPS = ("below", "above", "left_of", "right_of", "near")


class SelectorError(ValueError):
    """Selector resolution failed (zero or ambiguous matches, bad grammar)."""


class UnsupportedSelector(SelectorError):
    """Valid grammar that the v2 tree cannot evaluate (screen-space ops)."""


def flatten(tree: TreeNode) -> list[tuple[TreeNode, TreeNode | None]]:
    """Pre-order (node, parent) pairs; parents power the structural operators."""
    out: list[tuple[TreeNode, TreeNode | None]] = []

    def walk(node: TreeNode, parent: TreeNode | None) -> None:
        out.append((node, parent))
        for child in node.children:
            walk(child, node)

    walk(tree, None)
    return out


def _pattern_match(expected: str, actual: str) -> bool:
    if len(expected) >= 2 and expected.startswith("/") and expected.endswith("/"):
        return re.search(expected[1:-1], actual) is not None
    return expected == actual


def _matches(node: TreeNode, selector: dict[str, Any]) -> bool:
    if "name" in selector and not _pattern_match(str(selector["name"]), node.name):
        return False
    if "class" in selector and node.cls != selector["class"]:
        return False
    if "path" in selector and node.path != selector["path"]:
        return False
    if "text" in selector and (
        node.text is None or not _pattern_match(str(selector["text"]), node.text)
    ):
        return False
    if "group" in selector and str(selector["group"]) not in node.groups:
        return False
    return not ("visible" in selector and node.visible is not bool(selector["visible"]))


def resolve_selector(tree: TreeNode, selector: dict[str, Any]) -> TreeNode | None:
    """Resolve one selector dict against the tree, or raise SelectorError.

    With ``optional: true`` and zero matches, returns None (the only case
    where None is a valid answer).
    """
    for op in _SCREEN_SPACE_OPS:
        if op in selector:
            raise UnsupportedSelector(
                f"{op!r} needs projected bounds, which the v2 wire tree does "
                "not carry; use attribute or structural selectors instead"
            )
    optional = bool(selector.get("optional", False))
    nodes = flatten(tree)

    candidates = [node for node, _p in nodes if _matches(node, selector)]

    if "child_of" in selector:
        sub = selector["child_of"]
        candidates = [
            node
            for node, parent in nodes
            if _matches(node, selector) and parent is not None and _matches(parent, sub)
        ]
    if "contains" in selector:
        sub = selector["contains"]

        def _has_descendant(node: TreeNode) -> bool:
            return any(
                _matches(desc, sub) for desc, _p in flatten(node) if desc is not node
            )

        candidates = [n for n in candidates if _has_descendant(n)]

    names = [n.path for n in candidates]
    logger.info(
        "selector resolution: selector=%s candidates=%d %s",
        {k: v for k, v in selector.items() if k not in ("optional", "index")},
        len(candidates),
        names,
    )

    if not candidates:
        if optional:
            return None
        raise SelectorError(f"zero matches for selector {selector!r}")
    if "index" in selector:
        i = int(selector["index"])
        if i < 0 or i >= len(candidates):
            raise SelectorError(f"index {i} out of range for {len(candidates)} matches")
        return candidates[i]
    if len(candidates) > 1:
        raise SelectorError(
            f"ambiguous selector {selector!r}: {len(candidates)} matches "
            f"({names}); add an index (silently taking the first is how "
            "tests become non-deterministic)"
        )
    return candidates[0]
