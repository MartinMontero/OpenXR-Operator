"""Selector resolution tests (kit §5.3; flow contract)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from openxr_operator.godot_driver import _tree_from_dict
from openxr_operator.selectors import (
    SelectorError,
    UnsupportedSelector,
    resolve_selector,
)

TREE = _tree_from_dict(
    json.loads((Path(__file__).parent / "fixtures" / "demo_scene_tree.json").read_text())
)


def test_name_exact() -> None:
    node = resolve_selector(TREE, {"name": "StatusLabel"})
    assert node is not None and node.text == "STATUS: IDLE"


def test_multiple_matches_without_index_is_error() -> None:
    with pytest.raises(SelectorError, match="ambiguous"):
        resolve_selector(TREE, {"name": "/^Controller/"})


def test_index_disambiguates_deterministically() -> None:
    node = resolve_selector(TREE, {"name": "/^Controller/", "index": 1})
    assert node is not None and node.name == "ControllerRight"
    with pytest.raises(SelectorError, match="out of range"):
        resolve_selector(TREE, {"name": "/^Controller/", "index": 2})


def test_zero_matches_error_unless_optional() -> None:
    with pytest.raises(SelectorError, match="zero matches"):
        resolve_selector(TREE, {"name": "NoSuchNode"})
    assert resolve_selector(TREE, {"name": "NoSuchNode", "optional": True}) is None


def test_class_path_group_visible_attributes() -> None:
    origin = resolve_selector(TREE, {"class": "XROrigin3D"})
    assert origin is not None and origin.groups == ("xr_origin",)
    assert resolve_selector(TREE, {"path": "/root/Main/StatusLabel"}) is not None
    assert resolve_selector(TREE, {"group": "xr_origin"}) is not None
    assert resolve_selector(TREE, {"name": "StatusLabel", "visible": True}) is not None
    assert (
        resolve_selector(
            TREE, {"name": "StatusLabel", "visible": False, "optional": True}
        )
        is None
    )


def test_child_of_and_contains() -> None:
    cam = resolve_selector(TREE, {"class": "XRCamera3D", "child_of": {"group": "xr_origin"}})
    assert cam is not None
    with pytest.raises(SelectorError, match="zero matches"):
        # StatusLabel is a sibling of World, not a descendant.
        resolve_selector(TREE, {"name": "World", "contains": {"name": "StatusLabel"}})
    main = resolve_selector(TREE, {"name": "Main", "contains": {"name": "StatusLabel"}})
    assert main is not None


def test_screen_space_operators_raise_loudly() -> None:
    with pytest.raises(UnsupportedSelector, match="projected bounds"):
        resolve_selector(TREE, {"name": "StatusLabel", "below": {"name": "World"}})


def test_resolution_logged_with_candidate_set(caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level(logging.INFO, logger="openxr_operator.selectors"),
        pytest.raises(SelectorError),
    ):
        resolve_selector(TREE, {"name": "/^Controller/"})
    assert "candidates=2" in caplog.text
    assert "ControllerRight" in caplog.text
