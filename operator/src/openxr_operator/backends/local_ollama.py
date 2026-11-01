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


def _resolve_model_id(model: str) -> tuple[str, str | None]:
    """Map a configured model id to (request_model, digest_or_prefix).

    S-09 / escalation item 2d: Ollama rejects `name@sha256:<digest>` on
    /api/chat and /api/show (400 "invalid model name"). The content-addressed
    bare digest id IS accepted, and is the strongest pin. Translate:
    - `name@sha256:<64-hex>` -> request the 12-hex digest prefix; health
      checks the full digest against /api/tags entries.
    - a bare hex id (>=12 chars) is used as-is; health checks prefix match.
    - anything else is a tag (`:latest` appended if missing); no digest.
    """
    if "@sha256:" in model:
        digest = model.rsplit("@sha256:", 1)[1].lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ModelError(f"invalid digest in model id {model!r} (S-09)")
        return digest[:12], digest
    bare = model.lower()
    if len(bare) >= 12 and all(c in "0123456789abcdef" for c in bare):
        return bare, bare
    if ":" not in model:
        return model + ":latest", None
    return model, None


@register("local_ollama")
class OllamaBackend:
    backend_id = "local_ollama"

    def __init__(self, cfg: dict[str, Any]) -> None:
        self._host = str(cfg.get("host", DEFAULT_HOST)).rstrip("/")
        self._request_model, self._digest = _resolve_model_id(
            str(cfg.get("model", "qwen2.5vl:7b"))
        )
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
        entries = [m for m in body.get("models", []) if isinstance(m, dict)]
        if self._digest is not None:
            # Digest-pinned (S-09): match the content hash, not the tag.
            return any(
                str(m.get("digest", "")).lower().startswith(self._digest)
                for m in entries
            )
        names = {str(m.get("name", "")) for m in entries}
        return self._request_model in names

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
            "model": self._request_model,
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
            str(body.get("model", self._request_model)),
            self.backend_id,
            "native",
            time.monotonic_ns() - t0,
        )
