# W2-02-operator-driver — Wire client driver, capability gate, settle detector

| Field | Value |
|---|---|
| Wave | W2 |
| Owner | oxr-w-remote (reassigned from oxr-w-operator by human, 2026-10-30) |
| Writes | `operator/src/openxr_operator/godot_driver.py` (new), `operator/src/openxr_operator/settle.py` (new), `operator/tests/` |
| Depends on | W2-01-addon-server, W2-02-addon-capture, W2-03-addon-inject, W2-01-qa-demo-project (integration); unit work against a fake server starts immediately |
| Findings | F-004, F-012 (propagation), Maestro #2843 (settle); audit TC-SEC-004, TC-SEC-007; S-06 |
| Contracts | `docs/contracts/wire-protocol.md`, `driver.py`, `schema.py` (both read-only, orchestrator-owned) |

## Scope (delivered)

- Connect + token-first auth, protocol version in the auth frame; bad token,
  version mismatch, and pre-auth dispatch all raise AuthError.
- Request/response `id` matching; mismatched or unsolicited ids raise
  ProtocolError (F-017 companion).
- Capability gate (TC-SEC-004, F-004): every mutating command is validated
  through `schema.validate_action` BEFORE dispatch; rejected and logged;
  fake-server record proves nothing but the auth frame reaches the wire.
- Capture replies verified: declared tier match, sha256 of on-disk bytes,
  engine-reported black frame is an error, never an artifact.
- Bogus tracker failure propagates as TrackerBindError and is logged.
- Settle detector honours its timeout in both modes, measured ±50 ms.
  No `time.sleep`: waits are event-condition waits on threading.Event.
  `on_timeout` validated (S-15).
- S-06 measured (see below).

## Executed evidence (oxr-w-remote sandbox, 2026-10-30)

- `pytest -q` on the operator package: **50 passed, 1 skipped** (the skip is
  the marked real-addon integration test, per card; QA's contract-roundtrip
  replays it for real). Driver+settle deliver 21 of those tests.
- TC-SEC-004: `set_property`, `restart_scene`, `move_controller` with
  `capabilities: []` all raise ActionRejected; fake engine's received log
  contains only the auth frame; rejection logged.
- TC-SEC-007: alternating black/white frames, timeout_ms=300,
  interval_ms=50 — proceed and fail modes both return within ±50 ms of the
  deadline (asserted, not eyeballed).
- `ruff check src tests` clean and `ruff format --check` clean **with the
  CI-locked ruff 0.16.2** (not a newer local ruff).
- `mypy --strict src`: no issues found in 10 source files.
- `python3 tools/vendorscan.py`: clean.
- S-06 (qwen2.5 tokenizer, Qwen/Qwen2.5-7B tokenizer.json; tokenizers
  0.23.3): prompt with D-17 compact demo tree = 336 tokens, system = 12,
  one 768x432 frame ≈ 423 image tokens → **771 total vs 8192 num_ctx,
  7,421 tokens (~91%) headroom**. Tree alone: pretty 425 vs compact 263
  tokens. Full 1280x720 frame ≈ 1,175 tokens → downscale for act().
  Recorded in godot_driver.py S06_MEASUREMENT.

## Commits

- `aeec23a` — godot_driver.py + settle.py; fsguard format repair (locked
  ruff 0.16.2 also rejected the swept fsguard on main, i.e. main's format
  gate was red after 8cfc4e2; this commit fixes it).
- `d1d4967` — fake-engine driver tests, settle tests, demo tree fixture;
  P3-10 deep-nesting tests made interpreter-independent (5k-deep arrays
  parse fine on CPython 3.12 linux, so the original test only raised
  RecursionError on some builds; now 50k + a deterministic monkeypatched
  RecursionError mapping test).

## Notes for the orchestrator

- Integration with the real addon remains with W2-02-qa-contract-roundtrip
  (the marked test names it explicitly). This card is done on unit scope
  per its own "mark it, don't skip it silently" clause.
- `launch()` performs no destructive cleanup; `clean` is advisory and
  documented as belonging to the W3 runner.
