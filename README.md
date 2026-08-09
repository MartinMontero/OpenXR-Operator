# OpenXR Operator

A local-only AI agent that observes and drives Godot XR applications.

An in-engine Godot addon (MIT) instruments the running app; a Python agent
(AGPL-3.0-or-later) observes frames and scene trees over an authenticated
loopback channel, and acts through a declarative flow runner with
human-approved diffs on every mutation. Inference is local first, not local
only (D-12): local model backends are the default; hosted providers are
opt-in by manual configuration, one egress domain each, never an excluded
vendor (D-11), never automatic fallback (D-13). All model access goes through
the ModelBackend contract (D-10). No hosted component required.

**Canonical design:** `docs/BUILD_KIT_v3.pdf` (Kimi Code Swarm Edition).
**Build orchestration:** see `swarm/STATUS.md` and `docs/prompts/`.

## Status
Design audited and swarm-ready; implementation not started.
See `CHANGELOG.md` and the decision register (build kit Part 8).

## Layout
| Path | Licence | Contents |
|---|---|---|
| `addon/` | MIT | In-engine Godot addon (GDScript) |
| `layer/` | MIT | Optional OpenXR API layer (C++17/CMake), explicit + env-scoped only |
| `operator/` | AGPL-3.0-or-later | Python agent, flow runner, web UI |
| `docs/contracts/` | — | Five frozen contracts (wire protocol, Driver, action schema, flow schema, ModelBackend) |
| `flows/` | — | Declarative test flows |
| `tools/` | — | Gate enforcement (vendor scan, doc drift, action pinning) |
| `swarm/` | — | Agent coordination: task cards, requests, decisions, status |

## Gates (CI, all blocking)
Vendor gate (no Meta/OpenAI/xAI) · licence gate · bind gate (no 0.0.0.0) ·
implicit-layer gate · secrets (gitleaks) · SBOM + osv-scanner · format/lint/
types · GDScript parse · pytest · gdUnit4 · flow smoke (model disabled).

## Security model (non-negotiable)
Loopback-only binds · token-first auth on the engine port · browser never
touches the engine · model output is data (schema-validated, allowlisted,
diff-then-approve on mutations) · egress allowlist enforced outside the
agent process (default loopback only; a configured hosted backend opens
exactly one provider domain — the trade-off: every hosted adapter enabled is
a path by which a screenshot of your project and its scene tree leave the
machine, D-12) · permanent denylist for excluded-vendor endpoints, applied
after allowlist resolution, not configurable · hash-chained tamper-evident
audit log · explicit, environment-scoped OpenXR layer only.
