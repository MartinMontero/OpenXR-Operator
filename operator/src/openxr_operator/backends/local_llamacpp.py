"""Local adapter: llama.cpp / llama-server.

Speaks the OpenAI-compatible request shape, which the gate permits
(D-11: the shape is not an artifact). Images are content parts, not a
top-level array as in Ollama — that variance is why adapters exist.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from ..model import (
    Capabilities,
    ModelError,
    ModelResponse,
    encode_images,
    parse_model_response,
    render_user_text,
)
from . import register

DEFAULT_HOST = "http://127.0.0.1:8080"


@register("local_llamacpp")
class LlamaCppBackend:
    backend_id = "local_llamacpp"

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._host = str(cfg.get("host", DEFAULT_HOST)).rstrip("/")
        self._model = str(cfg.get("model", "local"))
        self._client = httpx.Client(timeout=float(cfg.get("timeout_s", 180)))

    def capabilities(self) -> Capabilities:
        return Capabilities(
            # json_schema (strict) on current llama-server; GBNF grammars on
            # older builds — both are provider-level constraint, hence native.
            # If a server build silently ignores response_format, the reply
            # fails parse_model_response loudly; it never pretends.
            constrained_decoding="native",
            supports_images=True,               # requires an mmproj build
            max_images_per_request=4,
            locality="local",
            egress_domain=None,
        )

    def health(self) -> bool:
        try:
            return self._client.get(
                f"{self._host}/health", timeout=5.0).status_code == 200
        except httpx.HTTPError:
            return False

    def act(self, system: str, task: str, scene_tree: dict[str, Any],
            image_paths: list[Path],
            schema: dict[str, Any]) -> ModelResponse:
        parts: list[dict[str, Any]] = [
            {"type": "text", "text": render_user_text(task, scene_tree)}]
        for b64 in encode_images(image_paths):
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": parts},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "action", "schema": schema,
                                "strict": True},
            },
        }
        t0 = time.monotonic_ns()
        try:
            r = self._client.post(f"{self._host}/v1/chat/completions",
                                  json=payload)
        except httpx.HTTPError as exc:
            raise ModelError(f"llama-server unreachable: {exc}") from exc
        if r.status_code != 200:
            raise ModelError(f"llama-server {r.status_code}: {r.text[:400]}")
        body = r.json()
        content = body["choices"][0]["message"]["content"]
        return parse_model_response(
            content, self._model, self.backend_id, "native",
            time.monotonic_ns() - t0)
