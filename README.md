# OpenXR Operator

**Build XR experiences by describing them.**

OpenXR Operator is an AI agent that watches your running Godot XR app,
understands its scene, and acts on it — moving controllers, navigating UI,
writing and fixing code — while you stay in charge. You describe what you
want in plain language; it proposes every change in plain language; nothing
happens until you approve it (D-14).

Inspired by Meta's XR Operator; built open and vendor-clean for Godot.
No coding required to use it. No hosted service required to run it.

## Who this is for
- **Creators (no code):** tell it what to build or fix. It sees your app,
  acts, and verifies — you approve each step in plain English.
- **XR developers:** the same loop, plus a declarative flow runner for
  repeatable, version-controlled test sessions.

## How it works (one paragraph)
An in-engine Godot addon (MIT) instruments the running app; a local Python
agent (AGPL-3.0-or-later) observes frames and scene trees over an
authenticated loopback channel and acts through a human-approved action
loop. Inference is local first, not local only (D-12): local model backends
are the default; hosted providers are opt-in by manual configuration, one
egress domain each, never an excluded vendor (D-11), never automatic
fallback (D-13). All model access goes through the ModelBackend contract
(D-10).

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
| `flows/` | — | Declarative test flows (saved artifacts; hand-writing never required) |
| `tools/` | — | Gate enforcement (vendor scan, doc drift, action pinning) |
| `swarm/` | — | Agent coordination: task cards, requests, decisions, status |

## Gates (CI, all blocking)
Vendor gate (no Meta/OpenAI/xAI) · licence gate · bind gate (no 0.0.0.0) ·
implicit-layer gate · secrets (gitleaks) · SBOM + osv-scanner · format/lint/
types · GDScript parse · pytest · gdUnit4 · flow smoke (model disabled).

## Security model (non-negotiable)
Loopback-only binds · token-first auth on the engine port · browser never
touches the engine · model output is data (schema-validated, allowlisted,
diff-then-approve on mutations — summarized in plain language, D-14) ·
egress allowlist enforced outside the agent process (default loopback only;
a configured hosted backend opens exactly one provider domain — the
trade-off: every hosted adapter enabled is a path by which a screenshot of
your project and its scene tree leave the machine, D-12) · permanent
denylist for excluded-vendor endpoints, applied after allowlist resolution,
not configurable · hash-chained tamper-evident audit log · explicit,
environment-scoped OpenXR layer only.
