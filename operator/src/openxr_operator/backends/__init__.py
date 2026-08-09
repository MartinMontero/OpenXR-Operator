"""Adapter registry. Resolution fails closed. (D-10/D-12/D-13)

Registration is explicit: shipped adapters are imported at the bottom of
this module so their @register decorators run. Registered-but-unshipped
adapters (LOCAL_IDS/HOSTED_IDS below) resolve to a named error, not a
silent fallback.
"""
from __future__ import annotations

from typing import Any, Callable

from ..model import (
    BackendRejected,
    ModelBackend,
    assert_host_allowed,
    assert_model_allowed,
    LOOPBACK_HOSTS,
)

_REGISTRY: dict[str, Callable[..., ModelBackend]] = {}

LOCAL_IDS = (
    "local_ollama", "local_llamacpp", "local_vllm", "local_lmstudio",
)
HOSTED_IDS = (
    "hosted_google", "hosted_mistral", "hosted_anthropic", "hosted_cohere",
    "hosted_deepseek", "hosted_alibaba", "hosted_together", "hosted_groq",
)
ALL_IDS = LOCAL_IDS + HOSTED_IDS


class ModelUnreachable(RuntimeError):
    pass


def register(backend_id: str) -> Callable[[Callable[..., ModelBackend]], Callable[..., ModelBackend]]:
    def deco(factory: Callable[..., ModelBackend]) -> Callable[..., ModelBackend]:
        _REGISTRY[backend_id] = factory
        return factory
    return deco


def resolve(cfg: dict[str, Any]) -> ModelBackend:
    """Build the configured backend or refuse to start.

    No fallback (D-13). If the configured backend is unreachable the run
    fails with a named error; it never silently switches backends.

    The permanent denylist is enforced HERE, centrally, after allowlist
    resolution — not delegated to each adapter's __init__ — so an adapter
    that omits the check cannot lapse the control (v2.1 audit, V-09).
    """
    backend_id = cfg.get("backend")
    if backend_id not in _REGISTRY:
        raise BackendRejected(
            f"unknown backend {backend_id!r}; "
            f"shipped: {sorted(_REGISTRY)}; registered: {sorted(ALL_IDS)}")

    model_id = str(cfg.get("model", ""))
    assert_model_allowed(model_id)

    allow = list(cfg.get("egress", {}).get("allow", []))
    backend = _REGISTRY[backend_id](cfg)
    caps = backend.capabilities()

    if caps.locality == "local":
        if allow:
            raise BackendRejected(
                f"{backend_id} is local; egress.allow must be empty")
        # A "local" adapter pointed off-loopback is nonsense and a hole.
        host = str(cfg.get("host", "")).split("://")[-1].split(":")[0].lower()
        if host and host not in LOOPBACK_HOSTS:
            raise BackendRejected(
                f"{backend_id} is local; host must be loopback, got {host!r}")
    else:
        if len(allow) != 1 or allow[0] != caps.egress_domain:
            raise BackendRejected(
                f"{backend_id} requires egress.allow == "
                f"['{caps.egress_domain}']; got {allow}")
        assert_host_allowed(allow[0], allow)  # unconditional denial, central

    if not backend.health():
        raise ModelUnreachable(
            f"backend {backend_id!r} unreachable; fix configuration. "
            "No automatic fallback is performed (D-13).")
    return backend


# Shipped adapters — imported so their @register decorators run.
from . import local_ollama  # noqa: F401,E402
from . import local_llamacpp  # noqa: F401,E402
