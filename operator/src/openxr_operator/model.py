"""Model backend contract (frozen). Mirrors ``driver.py`` on the engine side.

Provenance:
  sources: Build Kit v3.1 Part 2; kit v2.1 §3.5/§3.6/§4.4/§6.2 (harvested
           2026-08-09); decisions D-10 (backend policy), D-11 (gate scope),
           D-12 (locality), D-13 (fallback) — swarm/decisions/.
  verified: 2026-08-09 (py_compile, mypy --strict, vendorscan both directions)

D-10: ModelBackend(Protocol) with per-provider adapters, resolved fail-closed
through backends.resolve(). D-12: local first, not local only — hosted
providers are opt-in by manual configuration, one egress domain each.
D-13: no automatic fallback, ever.

Security posture: schema-constrained decoding is load-bearing (the capability
allowlist trusts parsed JSON). Every adapter declares how it constrains; a
response carries the mode actually applied, and anything below "native" must
be recorded in the run report as a degraded posture (kit §3.5).

The permanent denylist (FORBIDDEN_HOSTS) is not configuration. It is applied
centrally in backends.resolve() after allowlist resolution, so an adapter
that forgets to check cannot lapse the control (kit v2.1 audit, V-09).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

# How schema adherence was achieved for a response:
#   native          — the server constrained decoding (Ollama `format`,
#                     vLLM `guided_json`, llama.cpp json_schema/GBNF)
#   validate_retry  — server could not constrain; runner validated and
#                     retried once (degraded posture; report must say so)
#   none            — unconstrained (test doubles only; never in production)
ConstrainMode = Literal["native", "validate_retry", "none"]

Locality = Literal["local", "hosted"]

# Hosts denied unconditionally, after allowlist resolution. Not configurable,
# not overridable by a flow, a config file, or an env var. (D-11: the gate
# covers what these vendors make and run — servers, SDKs, models — not the
# JSON request shape one of them popularised.)
FORBIDDEN_HOSTS: frozenset[str] = frozenset(
    {
        "api.openai.com",  # vendorscan:gate-table
        "openai.com",  # vendorscan:gate-table
        "www.openai.com",  # vendorscan:gate-table
        "oai.azure.com",  # vendorscan:gate-table - OpenAI models via Azure
        "api.x.ai",  # vendorscan:gate-table
        "x.ai",  # vendorscan:gate-table - xAI
        "llama.meta.com",  # vendorscan:gate-table
        "llama-api.meta.com",  # vendorscan:gate-table - Meta
    }
)

# Model identifiers whose lineage fails the vendor gate, checked at startup.
# Substring match on the configured model id: hosted catalogues may carry
# excluded-lineage models even when the provider itself passes the gate.
# (vendorscan:gate-table applies to the tuple below.)
FORBIDDEN_MODEL_SUBSTRINGS: tuple[str, ...] = (
    "llama",  # vendorscan:gate-table
    "llava",  # vendorscan:gate-table
    "bakllava",  # vendorscan:gate-table
    "vicuna",  # vendorscan:gate-table
    "gpt-3",  # vendorscan:gate-table
    "gpt-4",  # vendorscan:gate-table
    "gpt-5",  # vendorscan:gate-table
    "o1-",  # vendorscan:gate-table
    "o3-",  # vendorscan:gate-table
    "o4-",  # vendorscan:gate-table
    "grok",  # vendorscan:gate-table
)

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class ModelError(RuntimeError):
    """Backend failure at call time. One retry is permitted, then abort."""


class BackendRejected(ValueError):
    """Raised at startup for a configuration that fails the gate."""


@dataclass(frozen=True)
class Capabilities:
    """What an adapter can prove, not what the provider claims on a card."""

    constrained_decoding: ConstrainMode
    supports_images: bool
    max_images_per_request: int
    locality: Locality
    egress_domain: str | None  # None for local


@dataclass(frozen=True)
class ModelResponse:
    raw: str
    parsed: dict[str, Any]
    model: str  # including digest pin where applicable
    backend_id: str
    constraint: ConstrainMode  # mode actually applied to this response
    duration_ns: int
    usage: dict[str, int] = field(default_factory=dict)


@runtime_checkable
class ModelBackend(Protocol):
    """The only surface the flow runner may use. The model is a client,
    not a component: the runner's suite passes with no backend at all."""

    backend_id: str

    def capabilities(self) -> Capabilities: ...

    def health(self) -> bool:
        """True if the backend is reachable and the model is available."""
        ...

    def act(
        self,
        system: str,
        task: str,
        scene_tree: dict[str, Any],
        image_paths: list[Path],
        schema: dict[str, Any],
    ) -> ModelResponse:
        """Send observation plus task; return a shape-validated response.

        Adapters that constrain decoding must apply `schema` at the provider
        level and report constraint="native". Adapters that cannot must
        report their actual mode; the runner records the degraded posture
        rather than pretending the constraint applied.
        """
        ...


def encode_images(paths: list[Path]) -> list[str]:
    return [base64.b64encode(p.read_bytes()).decode("ascii") for p in paths]


def render_user_text(task: str, scene_tree: dict[str, Any]) -> str:
    return (
        f"Task: {task}\n\n"
        f"Scene tree (JSON):\n{json.dumps(scene_tree, indent=2)}\n\n"
        "Reply with a single JSON object matching the required schema."
    )


def parse_model_response(
    content: str,
    model: str,
    backend_id: str,
    constraint: ConstrainMode,
    duration_ns: int,
) -> ModelResponse:
    """Shared response floor for every adapter: non-empty, JSON, an object."""
    if not content:
        raise ModelError("empty content from model")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ModelError(f"non-JSON from model: {content[:400]}") from exc
    if not isinstance(parsed, dict):
        raise ModelError("model returned JSON that is not an object")
    return ModelResponse(
        raw=content,
        parsed=parsed,
        model=model,
        backend_id=backend_id,
        constraint=constraint,
        duration_ns=duration_ns,
    )


def assert_host_allowed(host: str, allowlist: list[str]) -> None:
    """Allowlist first, then unconditional denial. Denial always wins."""
    h = host.lower().strip().rstrip(".")
    if h not in {a.lower() for a in allowlist}:
        raise BackendRejected(f"host {h!r} not in egress allowlist")
    for bad in FORBIDDEN_HOSTS:
        if h == bad or h.endswith("." + bad):
            raise BackendRejected(f"host {h!r} is permanently denied")


def assert_model_allowed(model_id: str) -> None:
    m = model_id.lower()
    for bad in FORBIDDEN_MODEL_SUBSTRINGS:
        if bad in m:
            raise BackendRejected(
                f"model {model_id!r} matches excluded lineage {bad!r}"
            )
