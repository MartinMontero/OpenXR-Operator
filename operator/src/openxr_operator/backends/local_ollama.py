"""Local adapter: Ollama (reference backend). Plain httpx, no vendor SDK."""

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

DEFAULT_HOST = "http://127.0.0.1:11434"


@register("local_ollama")
class OllamaBackend:
    backend_id = "local_ollama"

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._host = str(cfg.get("host", DEFAULT_HOST)).rstrip("/")
        self._model = str(cfg.get("model", "qwen2.5vl:7b"))
        # num_ctx is configuration, not a constant: W4 measures sufficiency
        # against the real demo scene tree and records the number (S-06).
        self._num_ctx = int(cfg.get("num_ctx", 8192))
        self._client = httpx.Client(timeout=float(cfg.get("timeout_s", 180)))

    def capabilities(self) -> Capabilities:
        return Capabilities(
            constrained_decoding="native",  # JSON Schema via `format` (R-4)
            supports_images=True,
            max_images_per_request=8,
            locality="local",
            egress_domain=None,
        )

    def health(self) -> bool:
        # P2-07: the contract says "reachable and the model is available".
        # Check /api/tags for the pinned model, not just server
        # reachability, so a missing model is a clear startup error
        # (D-13), not a mid-run 404 on the D-14 surface.
        try:
            r = self._client.get(f"{self._host}/api/tags", timeout=5.0)
        except httpx.HTTPError:
            return False
        if r.status_code != 200:
            return False
        try:
            body = r.json()
        except ValueError:
            return False
        if not isinstance(body, dict):
            return False
        names = {
            str(m.get("name", ""))
            for m in body.get("models", [])
            if isinstance(m, dict)
        }
        want = self._model.split("@", 1)[0]  # digest pin (S-09) is not a tag
        if ":" not in want:
            want += ":latest"
        return want in names

    def act(
        self,
        system: str,
        task: str,
        scene_tree: dict[str, Any],
        image_paths: list[Path],
        schema: dict[str, Any],
    ) -> ModelResponse:
        cap = self.capabilities()
        if len(image_paths) > cap.max_images_per_request:  # P2-09
            raise ModelError(
                f"{self.backend_id}: {len(image_paths)} images exceeds "
                f"max_images_per_request={cap.max_images_per_request}"
            )
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": render_user_text(task, scene_tree),
                    "images": encode_images(image_paths),
                },
            ],
            "stream": False,
            "format": schema,  # constrained decoding
            "options": {"temperature": 0, "num_ctx": self._num_ctx},
        }
        t0 = time.monotonic_ns()
        try:
            r = self._client.post(f"{self._host}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise ModelError(f"ollama unreachable: {exc}") from exc
        if r.status_code != 200:
            raise ModelError(f"ollama {r.status_code}: {r.text[:400]}")
        try:
            body = r.json()
        except ValueError as exc:
            raise ModelError("ollama: non-JSON HTTP body") from exc
        if not isinstance(body, dict):  # P2-08 class: unexpected 200 shape
            raise ModelError(f"ollama: unexpected response shape: {str(body)[:400]}")
        content = (body.get("message") or {}).get("content", "")
        return parse_model_response(
            content,
            str(body.get("model", self._model)),
            self.backend_id,
            "native",
            time.monotonic_ns() - t0,
        )
