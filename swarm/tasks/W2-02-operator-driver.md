# W2-02-operator-driver — Wire client driver, capability gate, settle detector

| Field | Value |
|---|---|
| Wave | W2 |
| Owner | oxr-w-operator |
| Writes | `operator/src/openxr_operator/godot_driver.py` (new), `operator/src/openxr_operator/settle.py` (new), `operator/tests/` |
| Depends on | W2-01-addon-server, W2-02-addon-capture, W2-03-addon-inject, W2-01-qa-demo-project (integration); unit work against a fake server starts immediately |
| Findings | F-004, F-012 (propagation), Maestro #2843 (settle); audit TC-SEC-004, TC-SEC-007; S-06 |
| Contracts | `docs/contracts/wire-protocol.md`, `driver.py`, `schema.py` (both read-only, orchestrator-owned) |

## Scope (RPI)

Implement the operator-side client of the wire protocol behind the `driver.py`
contract (new module; the contract file itself is not edited):

- Connect, auth per the contract (token from the engine's token file via
  fsguard-approved path), protocol version sent in the auth frame.
- Request/response `id` matching; mismatched or unsolicited ids are protocol
  errors (F-017 companion behavior).
- Capability gate (TC-SEC-004, F-004): every mutating command is validated
  against the flow's `capabilities` through `schema.validate_action` **before
  dispatch**. A well-formed action outside the flow's capabilities is
  rejected and logged; nothing reaches the wire.
- Capture replies carry `{path, tier, sha256}`; the driver verifies the tier
  matches the flow's declared `capture_tier` and the sha256 matches the file
  on disk before accepting the artifact.
- Bogus tracker raise from the engine propagates as a named driver error and
  is logged (W2 exit gate: bogus tracker raises — operator side).
- Settle detector (TC-SEC-007): honours its timeout in both modes (proceed
  and fail), measured ±50 ms. **No sleep anywhere** — settle waits on frame
  signals/event conditions, never wall-clock polling loops.
- S-06: measure `num_ctx` 8192 sufficiency against the real demo scene tree
  (tokenized with the qwen2.5 tokenizer, model not required); record the
  measured number and headroom in the module docstring or VERIFICATION input.

## Mandatory tests (executed evidence required)

- **TC-SEC-004:** well-formed `set_property` outside `capabilities: []` →
  rejected + logged; nothing sent (assert against a fake server socket).
- **TC-SEC-007:** settle timeout honoured — proceed mode and fail mode, each
  measured within ±50 ms of the deadline.
- Unit tests run against a fake in-process server; one integration test
  against the real addon lands after the addon cards (mark it, don't skip it
  silently).

## Constraints

mypy --strict, ruff clean, pytest green. Runner-side suite must pass with no
model backend at all (the model is a client, not a component).

## Done when

TCs executed green, S-06 number recorded, evidence pasted, commit(s) reference
`W2-02-operator-driver` and finding ids, card moved to `swarm/done/`.
