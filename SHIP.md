# SHIP — OpenXR Operator MVP status (2026-10-31)

## What is built and executed-tested

| Component | Evidence |
|---|---|
| Wire protocol v2, Driver, action schema, flow schema, ModelBackend (frozen contracts) | In repo; all consumers use them |
| Addon: token-first auth, limits, capture (T2/T3), A3 injection, editor bridge | gdUnit4 suites green on the build host (20/20 server, 4/4 render, 29/29 inject, 32/32 bridge) |
| `godot_driver.py` | Fake-engine WebSocket tests: auth, id-matching, capability-before-dispatch, tier/sha256/black verification, named TrackerBindError |
| `settle.py` | Timeout measured ±50 ms both modes (TC-SEC-007) |
| `selectors.py` / `flow.py` | Attribute+structural selectors; parse-time validation incl. S-15; deny-all preflight |
| `runner.py` / `artifacts.py` / `cli.py` | Full-stack executed run: YAML→runner→driver→engine→bundle+JUnit, CLI pass and failure paths |
| `approval.py` (D-14) | Plain-language cards for every mutating action; no auto-approve; rejections recorded |
| `auditlog.py` (S-08) | Hash chain; edit/delete/reorder detected; head anchor for truncation; secret redaction |
| `agent.py` | Approved mutation executes; rejection and capability violation never reach the wire; traversal blocked pre-approval; one-retry-then-abort |
| Web UI (M6) | Token required on every request; Origin allowlist on POST; CSP no third-party origins; D-14 cards in browser; approve executes / reject blocks, verified over real HTTP |
| `fsguard.py` | Absolute/.. /symlink/oversize all raise and log (TC-SEC-003) |

Python suite at last run: **123 passed, 2 marked skips**; ruff (locked
0.16.2) clean; mypy --strict clean; vendor gate clean; full-history gitleaks
clean.

## UNTESTED / open before real users

- **Real model-in-loop**: Ollama + qwen2.5vl:7b on the target hardware has
  not yet driven the agent loop end to end. S-09 digest pin and the W4
  latency measurement are outstanding.
- **Real addon ↔ real driver contract roundtrip** (QA card
  W2-02-qa-contract-roundtrip): unit fakes on both sides are green; the live
  pairing is the remaining proof.
- **ci.yml**: the GDScript parse step needs project context (item 2c) and
  the gdUnit4 flags (escalation §2/§2b), or CI goes red on infrastructure,
  not code.
- **XR hardware**: no headset test. Capture is T2/T3 (D-04); T1 is v2 scope.
- **Export-binary debugger cells**: UNTESTED (no export templates on host).
- **WCAG 2.2 AA formal audit**: keyboard/focus/empty/error states built in;
  no formal audit yet.
- **Fresh-clone install on a second machine**, and the D-14 non-developer
  usability pass with a real non-developer.
- **assign_script execution** is deliberately not wired yet (editor bridge
  integration); it raises a named error, never a silent no-op.

## Residual risks

- CPU inference on the measured floor (Ryzen 5 7530U) is single-digit
  tokens/sec; the UI is designed around that (queued approvals, no
  streaming promises), but W4 must record real numbers.
- Token at rest is plaintext (documented; the threat model is browser →
  engine, not local processes).
- Prompt injection is reduced, not eliminated (D-17 delimiting). The schema,
  capability, containment, and approval gates remain the load-bearing
  controls.
