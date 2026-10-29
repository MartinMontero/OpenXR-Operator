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
