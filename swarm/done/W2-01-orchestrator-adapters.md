# W2-01-orchestrator-adapters — Adapter robustness trio + parse guards (contract area)

| Field | Value |
|---|---|
| Wave | W2 |
| Owner | **orchestrator** (P-2 excludes `backends/` and `model.py` from oxr-w-operator ownership; these fixes live in both) |
| Writes | `operator/src/openxr_operator/backends/local_ollama.py`, `operator/src/openxr_operator/backends/local_llamacpp.py`, `operator/src/openxr_operator/model.py`, `operator/tests/` |
| Depends on | — |
| Findings | audit P2-07 (TC-QA-012), P2-08, P2-09, P3-10 |

## Scope (RPI)

External audit 2026-08-11, remediation item 2. Small, contract-adjacent:

- **P2-07** — `OllamaBackend.health()` checks `/api/tags` for the pinned model
  (exact `name:tag`, `:latest` when untagged), not just reachability. Contract
  docstring already says "reachable and the model is available" — this aligns
  code with contract; no signature change. **TC-QA-012:** fake `/api/tags`
  bodies → model present True, absent False, server down False.
- **P2-08** — llama.cpp `act()`: `body["choices"][0]["message"]["content"]`
  wrapped; `KeyError/IndexError/TypeError` → named `ModelError` with the first
  400 chars of the body. `r.json()` wrapped in both adapters: `ValueError` →
  `ModelError("non-JSON HTTP body")`.
- **P2-09** — `max_images_per_request` enforced first line of `act()` in both
  adapters (8 Ollama, 4 llama.cpp); over-limit → `ModelError` naming the limit.
- **P3-10** — `parse_model_response` guards: reject `len(content) > 1_000_000`
  before parsing; catch `RecursionError` alongside `JSONDecodeError` →
  `ModelError`. `model.py` is a frozen contract: same handling as D-17 —
  file the amendment note in `swarm/requests/`, orchestrator rules, record in
  `swarm/decisions/`.

## Mandatory tests

TC-QA-012 plus: over-limit images raise (both adapters); malformed 200 body →
`ModelError` (not `KeyError`); non-JSON body → `ModelError`; oversize content
rejected pre-parse; deep nesting → `ModelError` (not `RecursionError`).

## Done when

Tests executed green, P3-10 amendment recorded, evidence pasted, commit(s)
reference `W2-01-orchestrator-adapters` and the finding ids, card moved to
`swarm/done/`.

## Executed evidence (2026-10-29)

All local, offline, deterministic (httpx.Client monkeypatched with a stub).
Suite: `uv run --project operator pytest -q` -> **31 passed** (15 new in
`operator/tests/test_adapters.py`); ruff format --check, ruff check,
mypy --strict, vendor gate all green.

| Finding | Tests (all executed green) |
|---|---|
| P2-07 / TC-QA-012 | `test_health_true_when_pinned_model_present`, `test_health_false_when_model_absent`, `test_health_false_when_server_down`, `test_health_false_on_non_json_tags`, `test_health_defaults_to_latest_tag`, `test_health_ignores_digest_pin_for_tag_lookup` |
| P2-09 | `test_ollama_rejects_over_limit_images` (9 > 8), `test_llamacpp_rejects_over_limit_images` (5 > 4) |
| P2-08 | `test_llamacpp_unexpected_200_shape_is_model_error`, `test_llamacpp_non_json_body_is_model_error`, `test_ollama_non_json_body_is_model_error`, `test_ollama_non_dict_body_is_model_error` |
| P3-10 / D-18 | `test_parse_rejects_oversize_content` (1,000,001 chars), `test_parse_deep_nesting_is_model_error_not_recursion_error` (5000-deep), `test_parse_valid_object_unchanged` |

Contract handling: P3-10 touched frozen `model.py` and went through
`swarm/requests/contract-amendment-P3-10-parse-guards.md`, ruled APPROVED,
recorded as `swarm/decisions/D-18.md`. P2-07 aligned `health()` with the
contract's existing "reachable and the model is available" wording - code
changed, contract text did not.
