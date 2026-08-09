"""Model backend contract (frozen). Mirrors ``driver.py`` on the engine side.

Provenance:
  sources: Build Kit v3.0 Part 2; kit v2.0 §3.5/§4.4 defect analysis (2026-08-09);
           decisions D-09 (protocol + multiple adapters) and D-10 (vendor gate
           covers artifacts, not wire formats) — swarm/decisions/.
  verified: 2026-08-09

D-09 rationale: kit v2.0 shipped a concrete ``OllamaClient`` with no seam,
while the engine side got ``Driver(Protocol)`` — same problem, opposite
treatment. This file is the model-side seam. Ollama is the reference backend,
not the only one.

Security posture: schema-constrained decoding is load-bearing (the capability
allowlist trusts parsed JSON). Every backend declares how it constrains; if a
backend can only validate-and-retry, that fact travels on the response and
into the run report. Egress targets come from configuration, never from a
literal in this file (kit v2.0 §3.6 hardcoded a port — that was the defect).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

import httpx

# How schema adherence was achieved for a response:
#   native          — the server constrained decoding (Ollama `format`,
#                     vLLM `guided_json`, llama.cpp GBNF)
#   validate_retry  — server could not constrain; runner validated and
#                     retried once (degraded posture; report must say so)
#   none            — unconstrained (test doubles only; never in production)
ConstrainMode = Literal["native", "validate_retry", "none"]


class ModelError(RuntimeError):
    """Backend failure. One retry is permitted by the caller, then abort."""


@dataclass(frozen=True)
class BackendCapabilities:
    """What a backend can prove, not what it claims on its model card."""

    supports_images: bool
    constrained_decoding: ConstrainMode
    digest_pinning: bool  # can the model revision be pinned by content digest


@dataclass(frozen=True)
class ModelResponse:
    raw: str
    parsed: dict[str, Any]
    model: str  # including digest pin, e.g. "qwen2.5vl:7b@sha256:..."
    backend: str  # adapter name, e.g. "ollama"
    duration_ns: int
    constraint: ConstrainMode


@runtime_checkable
class ModelBackend(Protocol):
    """The only surface the flow runner may use. The model is a client,
    not a component: the runner's suite passes with no backend at all."""

    def capabilities(self) -> BackendCapabilities: ...

    def health(self) -> bool: ...

    def chat_with_images(
        self,
        *,
        messages: list[dict[str, Any]],
        images: list[bytes],
        schema: dict[str, Any],
        temperature: float = 0.0,
        timeout_s: float = 180.0,
    ) -> ModelResponse: ...


class OllamaBackend:
    """Reference adapter: Ollama native API over plain httpx (no vendor SDK).

    Host comes from configuration (operator settings / env), defaulting to
    loopback. The egress allowlist in deployment config names the host:port;
    nothing is hardcoded here beyond the loopback default.
    """

    NAME = "ollama"
    DEFAULT_HOST = "http://127.0.0.1:11434"

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        model: str = "qwen2.5vl:7b",  # pin by digest in production config
        timeout_s: float = 180.0,
    ) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._client = httpx.Client(timeout=timeout_s)

    def close(self) -> None:
        self._client.close()

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_images=True,          # R-4: format composes with images
            constrained_decoding="native",  # JSON Schema via `format`
            digest_pinning=True,           # ollama pull model@sha256:...
        )

    def health(self) -> bool:
        try:
            r = self._client.get(f"{self._host}/api/tags")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def chat_with_images(
        self,
        *,
        messages: list[dict[str, Any]],
        images: list[bytes],
        schema: dict[str, Any],
        temperature: float = 0.0,
        timeout_s: float = 180.0,
    ) -> ModelResponse:
        import base64
        import json
        import time

        msgs = [dict(m) for m in messages]
        if images:
            # Ollama takes a bare base64 array on the final user message
            # (OpenAI-compatible `image_url` parts are a different shape —
            # that variance is why adapters exist).
            msgs[-1]["images"] = [base64.b64encode(b).decode() for b in images]
        payload = {
            "model": self._model,
            "messages": msgs,
            "format": schema,
            "stream": False,
            "options": {"temperature": temperature},
        }
        t0 = time.monotonic_ns()
        try:
            r = self._client.post(f"{self._host}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise ModelError(f"ollama chat failed: {exc}") from exc
        body = r.json()
        raw = body.get("message", {}).get("content", "")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            # Native constraint should make this unreachable; if reached,
            # the backend is not honouring `format` — fail loud, do not retry silently.
            raise ModelError(f"unparseable model output under native constraint: {exc}") from exc
        return ModelResponse(
            raw=raw,
            parsed=parsed,
            model=self._model,
            backend=self.NAME,
            duration_ns=time.monotonic_ns() - t0,
            constraint="native",
        )


# Backend register (D-09). Same shape as the dependency register: licence
# and gate status stated, not assumed. Adapters land in their build waves;
# an entry here is a commitment to evaluate, not shipped code.
BACKEND_REGISTER: tuple[dict[str, str], ...] = (
    {
        "name": "ollama",
        "adapter": "OllamaBackend (this file)",
        "status": "reference, shipped",
        "constrained_decoding": "native (format: JSON Schema)",
        "gate": "pass — no vendor artifact; local server",
    },
    {
        "name": "llama.cpp / llama-server",
        "adapter": "planned",
        "status": "registered, not shipped",
        "constrained_decoding": "native (GBNF grammar)",
        "gate": "evaluate on adoption — MIT server; model lineage per weights",
    },
    {
        "name": "openai-compatible (vLLM, LM Studio, LocalAI)",
        "adapter": "planned",
        "status": "registered, not shipped",
        "constrained_decoding": "varies (guided_json / response_format); adapter must declare",
        "gate": "D-10: wire format is not an artifact — plain httpx only, no openai package",
    },
)
