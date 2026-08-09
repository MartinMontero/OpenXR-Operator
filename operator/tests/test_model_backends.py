"""Fail-closed resolution tests for the ModelBackend contract (D-10..D-13).

No model server is required: every case must be rejected before or at the
health check. The health-check case points at the discard port (9), where
nothing listens, so refusal is immediate and deterministic.
"""

from __future__ import annotations

import pytest

from openxr_operator.backends import ModelUnreachable, resolve
from openxr_operator.model import (
    BackendRejected,
    assert_host_allowed,
    assert_model_allowed,
)


def _cfg(**over: object) -> dict:
    cfg: dict = {
        "backend": "local_ollama",
        "model": "qwen2.5-vl:7b",
        "host": "http://127.0.0.1:9",
        "egress": {"allow": []},
    }
    cfg.update(over)
    return cfg


def test_unknown_backend_rejected_listing_options() -> None:
    with pytest.raises(BackendRejected, match="unknown backend"):
        resolve(_cfg(backend="hosted_openai"))


def test_registered_but_unshipped_backend_is_named_error_not_fallback() -> None:
    with pytest.raises(BackendRejected, match="unknown backend"):
        resolve(_cfg(backend="hosted_google"))


def test_meta_lineage_model_rejected_at_startup() -> None:
    with pytest.raises(BackendRejected, match="excluded lineage"):
        resolve(_cfg(model="llama-3.2-11b-vision"))


def test_local_backend_pointed_off_loopback_rejected() -> None:
    with pytest.raises(BackendRejected, match="loopback"):
        resolve(_cfg(host="http://192.168.1.50:11434"))


def test_local_backend_with_egress_allow_rejected() -> None:
    with pytest.raises(BackendRejected, match="egress.allow must be empty"):
        resolve(_cfg(egress={"allow": ["127.0.0.1"]}))


def test_permanent_denylist_beats_allowlist() -> None:
    with pytest.raises(BackendRejected, match="permanently denied"):
        assert_host_allowed("api.openai.com", ["api.openai.com"])


def test_denylist_catches_subdomains() -> None:
    with pytest.raises(BackendRejected, match="permanently denied"):
        assert_host_allowed("evil.api.openai.com", ["evil.api.openai.com"])


def test_allowlist_miss_rejected_before_denial() -> None:
    with pytest.raises(BackendRejected, match="not in egress allowlist"):
        assert_host_allowed("example.com", ["other.example.com"])


def test_model_lineage_substrings() -> None:
    for bad in ("gpt-4o", "grok-2", "vicuna-13b"):
        with pytest.raises(BackendRejected):
            assert_model_allowed(bad)
    assert_model_allowed("qwen2.5-vl:7b")  # permitted lineage passes


def test_unreachable_backend_is_named_error_no_fallback() -> None:
    with pytest.raises(ModelUnreachable, match="No automatic fallback"):
        resolve(_cfg())
