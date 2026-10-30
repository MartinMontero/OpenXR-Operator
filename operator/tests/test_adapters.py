"""Adapter robustness tests (W2-01-orchestrator-adapters).

Audit findings P2-07 (TC-QA-012), P2-08, P2-09, P3-10 (D-18). No model
server is required: httpx.Client is monkeypatched with a stub, so every
case is deterministic and offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from openxr_operator.backends.local_llamacpp import LlamaCppBackend
from openxr_operator.backends.local_ollama import OllamaBackend
from openxr_operator.model import ModelError, parse_model_response


class _Resp:
    def __init__(
        self, status: int = 200, payload: Any = None, *, bad_json: bool = False
    ) -> None:
        self.status_code = status
        self._payload = payload
        self._bad_json = bad_json
        self.text = "" if payload is None else str(payload)

    def json(self) -> Any:
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


class _Client:
    def __init__(self, resp: _Resp | None = None, exc: Exception | None = None) -> None:
        self._resp = resp
        self._exc = exc

    def get(self, url: str, timeout: float = 0.0) -> _Resp:
        if self._exc is not None:
            raise self._exc
        assert self._resp is not None
        return self._resp

    def post(self, url: str, json: Any = None) -> _Resp:
        if self._exc is not None:
            raise self._exc
        assert self._resp is not None
        return self._resp


def _ollama(
    monkeypatch: pytest.MonkeyPatch,
    resp: _Resp | None = None,
    exc: Exception | None = None,
    model: str = "qwen2.5vl:7b",
) -> OllamaBackend:
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _Client(resp, exc))
    return OllamaBackend({"model": model})


def _llamacpp(
    monkeypatch: pytest.MonkeyPatch,
    resp: _Resp | None = None,
    exc: Exception | None = None,
) -> LlamaCppBackend:
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _Client(resp, exc))
    return LlamaCppBackend({"model": "local"})


# --- P2-07 / TC-QA-012: health() means the pinned model is available --------


def test_health_true_when_pinned_model_present(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _Resp(payload={"models": [{"name": "qwen2.5vl:7b"}, {"name": "x:latest"}]})
    assert _ollama(monkeypatch, resp).health() is True


def test_health_false_when_model_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _Resp(payload={"models": [{"name": "qwen2.5vl:3b"}]})
    assert _ollama(monkeypatch, resp).health() is False


def test_health_false_when_server_down(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _ollama(monkeypatch, exc=httpx.ConnectError("refused"))
    assert b.health() is False


def test_health_false_on_non_json_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _ollama(monkeypatch, _Resp(bad_json=True)).health() is False


def test_health_defaults_to_latest_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _Resp(payload={"models": [{"name": "qwen2.5vl:latest"}]})
    assert _ollama(monkeypatch, resp, model="qwen2.5vl").health() is True


def test_health_ignores_digest_pin_for_tag_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resp = _Resp(payload={"models": [{"name": "qwen2.5vl:7b"}]})
    b = _ollama(monkeypatch, resp, model="qwen2.5vl:7b@sha256:" + "0" * 64)
    assert b.health() is True


# --- P2-09: declared max_images_per_request is enforced ----------------------


def test_ollama_rejects_over_limit_images(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _ollama(monkeypatch, _Resp(payload={}))
    with pytest.raises(ModelError, match="max_images_per_request=8"):
        b.act("sys", "task", {}, [Path("x.png")] * 9, {})


def test_llamacpp_rejects_over_limit_images(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _llamacpp(monkeypatch, _Resp(payload={}))
    with pytest.raises(ModelError, match="max_images_per_request=4"):
        b.act("sys", "task", {}, [Path("x.png")] * 5, {})


# --- P2-08: unexpected 200 shapes are named ModelErrors ----------------------


def test_llamacpp_unexpected_200_shape_is_model_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    b = _llamacpp(monkeypatch, _Resp(payload={"unexpected": True}))
    with pytest.raises(ModelError, match="unexpected response shape"):
        b.act("sys", "task", {}, [], {})


def test_llamacpp_non_json_body_is_model_error(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _llamacpp(monkeypatch, _Resp(bad_json=True))
    with pytest.raises(ModelError, match="non-JSON"):
        b.act("sys", "task", {}, [], {})


def test_ollama_non_json_body_is_model_error(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _ollama(monkeypatch, _Resp(bad_json=True))
    with pytest.raises(ModelError, match="non-JSON"):
        b.act("sys", "task", {}, [], {})


def test_ollama_non_dict_body_is_model_error(monkeypatch: pytest.MonkeyPatch) -> None:
    b = _ollama(monkeypatch, _Resp(payload=["not", "a", "dict"]))
    with pytest.raises(ModelError, match="unexpected response shape"):
        b.act("sys", "task", {}, [], {})


# --- P3-10 / D-18: parse guards ----------------------------------------------


def test_parse_rejects_oversize_content() -> None:
    with pytest.raises(ModelError, match="oversize content"):
        parse_model_response(" " * 1_000_001, "m", "b", "native", 0)


def test_parse_deep_nesting_is_model_error_not_recursion_error() -> None:
    # Interpreter-independent: CPython's scanner raises RecursionError at
    # different depths by build (3.13 win: 5k; 3.12 linux: >5k, <50k). Either
    # way the caller must see ModelError, never a raw RecursionError.
    deep = "[" * 50_000 + "]" * 50_000
    with pytest.raises(ModelError):
        parse_model_response(deep, "m", "b", "native", 0)


def test_parse_recursion_error_is_mapped_to_model_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Deterministic guard check: force the parser failure itself.
    def _boom(_s: str) -> object:
        raise RecursionError

    monkeypatch.setattr(json, "loads", _boom)
    with pytest.raises(ModelError, match="too deeply nested"):
        parse_model_response("{}", "m", "b", "native", 0)


def test_parse_valid_object_unchanged() -> None:
    r = parse_model_response('{"a": 1}', "m", "b", "native", 0)
    assert r.parsed == {"a": 1}
