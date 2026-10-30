# Contract amendment request — P3-10: size/depth guards in `parse_model_response`

| Field | Value |
|---|---|
| Submitted | 2026-10-29 |
| Source | External audit 2026-08-11 (`swarm/requests/external-audit-2026-08-11.md`), finding P3-10; card `swarm/tasks/W2-01-orchestrator-adapters.md` |
| Frozen artifact touched | `operator/src/openxr_operator/model.py` — `parse_model_response()` |
| Signature change | **None.** Same parameters, same return type. Failure behaviour changes: two previously-uncaught exception classes become named `ModelError`s. |
| Ruling requested from | orchestrator (same pattern as D-17) |

## Problem (from the audit)

`parse_model_response` is the shared response floor for every adapter,
including future hosted ones (D-15's Kimi among them). Today:

- `content` is unbounded — parsed in memory whatever its size.
- Deeply nested JSON raises an uncaught `RecursionError`, escaping the
  runner's `ModelError` retry-once-then-abort logic.

Risk today is low (local model), but the function is the floor for 12 future
adapters; the guards are cheapest now, at contract level.

## Proposed amendment

```python
def parse_model_response(...) -> ModelResponse:
    if not content:
        raise ModelError("empty content from model")
    if len(content) > 1_000_000:
        raise ModelError(
            f"oversize content from model: {len(content)} chars (limit 1_000_000)"
        )
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ModelError(f"non-JSON from model: {content[:400]}") from exc
    except RecursionError as exc:
        raise ModelError("model JSON too deeply nested") from exc
    ...
```

## Required tests

- Content of 1,000,001 chars → `ModelError` (rejected before parsing).
- Deeply nested JSON → `ModelError`, never `RecursionError`.
- Existing behaviour unchanged: non-JSON and non-object still `ModelError`.

## Ruling

**APPROVED — orchestrator, 2026-10-29.** Recorded as swarm/decisions/D-18.md.

Rationale: signature unchanged; the change converts uncaught crashes into the
named `ModelError` the runner's retry logic already expects — it strengthens
the failure contract without weakening any gate. No human stop triggered.
Implemented with the required tests in the same commit.
