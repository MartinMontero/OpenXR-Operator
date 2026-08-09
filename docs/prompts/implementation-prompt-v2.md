# Production Implementation & Hardening — OpenXR Operator (v2.0)

**What this file is.** A hardened, domain-specialized successor to the generic *Production-ready code review and optimization* prompt, adapted to the OpenXR Operator project and wired to its companion audit (*Adversarial QA & Production-Readiness Audit — OpenXR Operator v3.0*). It supersedes both the generic prompt and the build kit's own §9.2 kickoff prompt. Section 1 documents what changed and why. Section 2 is the research baseline, verified 9 August 2026. Section 3 is the paste-ready implementation prompt.

**Relationship to the audit prompt.** The audit prompt (v3.0) finds everything that would fail; this prompt builds and hardens. They share the epistemic model, the gates, and the finding/amendment ledger format, so the outputs of one are machine-consumable inputs to the other. Run the audit first; this prompt consumes its amendments. If no audit has been run, Phase 0 below does a compressed one before any code is written.

---

## 1. Adaptation analysis — what v2.0 changes and why

### 1.1 Holes in the generic prompt (fixed)

| Hole | Fix in v2.0 |
|---|---|
| **Web-app assumptions baked into the DoD** (console errors, `dangerouslySetInnerHTML`, responsive breakpoints, Cloudflare Pages default). Meaningless for a Godot addon + Python agent + C++ OpenXR layer. | DoD rewritten per plane: engine (GDScript parse, debugger errors), agent (mypy strict, pytest), layer (compiler warnings-as-errors, explicit-layer gate), web UI (the only place CSP/responsive/a11y apply). Cloudflare default removed — the deploy target is a developer workstation. |
| **No toolchain preflight.** "Build and run it" assumes the toolchain exists and works. For this project the sandbox mechanism itself (bubblewrap) can fail with EPERM on hosts where AppArmor restricts unprivileged user namespaces — silently losing a security layer if unchecked. | New **Phase 0 — Preflight**: verify every tool on the actual host, including a bubblewrap smoke test, GPU/VRAM inventory against the resource envelope, and a hardware-floor check before any planning. Sandbox degradation must be loud, never silent. |
| **"UNTESTED" is the only epistemic label.** | Adopts the four-state model (CONFIRMED / INFERRED / BLOCKED / NOT ATTEMPTED) from the audit, plus UNTESTED for build claims. Presenting NOT ATTEMPTED as BLOCKED is a report defect. |
| **No re-verification of time-sensitive stack claims.** "Verify current best practices" is one bullet with no checklist. | Phase 1 carries the audit's Annex B re-verification schedule (engine version, issue #100004, LNA enforcement, Ollama structured outputs, model licences, tool versions) — every row dated as of build day. |
| **"No approval gate unless Rule 9 triggers"** is acceptable for a web prototype but wrong here: this project's entire security model is a human-in-the-loop approval gate for mutating agent actions. | The approval gate is a *product feature under construction*, not a process inconvenience. It must be built, tested to be unbypassable, and never flagged off (kit D-06). Separate explicit **human stop points** are added for M7/D-04 and gate changes. |
| **Verification loop is web-centric** ("play through every user flow", "no console errors"). | Rewritten: every declarative flow in `flows/`, model-disabled (deterministic) then model-enabled; per-step capture tier and settle outcome recorded; engine debugger monitored for errors. The generic prompt's own flaky-async note is made concrete: XR/frame-timing surfaces get **three** consecutive clean runs; static surfaces two. |
| **No supply-chain execution detail.** "osv-scanner, never Trivy" is inherited policy with no teeth. | Pin every GitHub Action by commit digest (the audit's S-01), checksum-verify every downloaded binary (S-10), pin model weights by digest (S-09), `uv sync --frozen` everywhere. |
| **No relationship to a prior audit or a design kit.** The generic prompt assumes a bare repo. | v2.0 consumes three inputs explicitly: the build kit (canonical design), the v3.0 audit outputs (findings F-###, amendments A-##, decisions D-##), and the repo. Amendments apply first, in dependency order. |

### 1.2 Holes in the kit's own §9.2 kickoff prompt (fixed)

1. **No preflight.** §9.2 jumps to repo mapping. It never checks that Godot 4.7.x, uv, Ollama, CMake, or the sandbox mechanism actually work on the build host — so a broken bubblewrap or an absent GPU is discovered at M5, not minute 5.
2. **No resource-envelope step.** Nothing ever measures VRAM/RAM/latency against a stated floor (audit suspect S-11). Phase 0 and the DoD now require it.
3. **CI invocation correctness is unexamined.** §7.2's workflow runs `godot --headless --path demo_project -s addons/gdUnit4/bin/GdUnitCmdTool.gd` — with `--path demo_project`, the script path resolves against *that* project, so gdUnit4 must be installed in the demo project, and a fresh CI checkout needs a `--import` pass first or resource import fails. `--check-only` requires `--script` and headless, and surfaces errors only — warnings need `--debug` (which can drop into the debugger and hang CI without a timeout) or gdlint. Phase 0 verifies every CI command actually runs before Phase 3 relies on it.
4. **No instruction to disposition the audit's seeded suspects.** §9.2 maps fixes to the kit's F-### ledger only. v2.0 adds the audit's F-1## findings and S-01…S-16 suspects to the plan mapping.
5. **Model supply chain absent.** §9.2 never pins model weights. `ollama pull` without a digest is an unpinned dependency in the security-critical path — now a gate.
6. **Verification loop lacks tier evidence.** §9.2 logs pass/fail per flow but doesn't require the capture tier and settle outcome per step — the exact data needed to catch a silent fidelity downgrade (the tier-honesty gate).

---

## 2. Research baseline addendum (verified 9 August 2026)

Build-mechanics facts this prompt depends on. Re-verify each on build day (Phase 1, Annex B schedule).

| # | Fact | Status | Evidence |
|---|---|---|---|
| R-9 | `godot --check-only` only parses errors, requires `--script` and (on display-less platforms) `--headless`; warnings require `--debug`, which can drop into the debugger — wrap every Godot CLI call in CI with a timeout. | CONFIRMED | Godot command-line docs; forum confirmation [^1^][^2^] |
| R-10 | gdUnit4 v6.2.x runs headless via `godot --headless --path <project> -s res://addons/gdUnit4/bin/GdUnitCmdTool.gd` with JUnit/HTML report output; v6.2.0+ is the line that supports Godot 4.7/4.7.1. A fresh checkout needs a `--import` pass before tests. | CONFIRMED | gdUnit4 repo and asset page [^3^][^4^] |
| R-11 | bubblewrap relies on unprivileged user namespaces; on kernels with `apparmor_restrict_unprivileged_userns=1` (Ubuntu 24.04 line) sandbox preflight can fail EPERM. Preflight test and loud fallback are mandatory; the sandbox policy lives in the bwrap arguments, not the tool. | CONFIRMED | bubblewrap README; reproduced preflight failure [^5^][^6^] |
| R-12 | `uv sync --frozen` is the CI-standard reproducible install; `uv lock --check` fails on a stale lockfile. | CONFIRMED | uv documentation/workflow references [^7^] |
| R-13 | Godot 4.7.1 (14 Jul 2026) is the current maintenance release; pin CI to 4.7.1, state a 4.8 policy. | CONFIRMED | godotengine.org [^8^] |

---

## 3. The implementation prompt (paste-ready)

Everything below the rule is the deliverable prompt. Paste into Claude Code (or equivalent agent) at the repository root.

---

# Mission

Take the OpenXR Operator from design-complete to production-ready, shippable state. Three inputs are canonical, in this order of authority:

1. **The build kit** (`docs/BUILD_KIT.pdf`, source in `docs/kit/`) — architecture, tier model, security design, licence split. Refine execution, do not redesign.
2. **The v3.0 audit outputs** (`AUDIT.md` findings F-###/F-1##, amendments A-##, decisions D-##) — apply amendments first, in their stated dependency order. If the audit has not been run, run Phase 0's compressed audit before anything else.
3. **The repo as it exists** — actual behaviour outranks both documents where they disagree; log every such disagreement in AUDIT.md.

Where intent is ambiguous, follow the dominant pattern already in the kit and log the ambiguity; do not invent a new direction.

# Operating rules

1. **RPI:** Research → Plan → Implement. No code changes until AUDIT.md and PLAN.md exist on disk.
2. **Rule 9:** no destructive or irreversible action (force-push, history rewrite, file/branch deletion, dependency removal) without listing it first and getting explicit approval.
3. **Zero fabrication.** Every claim in every report is backed by something you ran, read, or can cite from a primary source. Labels: CONFIRMED (ran it / primary source, dated), INFERRED (reasoning shown), BLOCKED (what you tried, how it failed), NOT ATTEMPTED (said plainly), UNTESTED (for build claims). Never write "could not confirm" for something you did not attempt.
4. **Licence split is invariant:** `addon/` and `layer/` MIT, `operator/` AGPL-3.0-or-later, repo default AGPL-3.0-or-later. Keep `LICENSES/` and `NOTICE` accurate on every dependency change.
5. **Vendor gate:** no Meta, OpenAI, or xAI dependency, direct or transitive — SDKs, models, model lineage and training-data provenance, APIs, infra. Google permitted. `tools/vendorscan.py` enforces this and must stay green.
6. **Security gates are invariant:** loopback-only binds; explicit environment-scoped OpenXR layer only (never implicit.d, never registry writes); no browser-reachable path to the engine port; no mutating agent action without a human-approved diff. Each is a CI gate; weakening one requires explicit human approval (Rule 9 applies).
7. **Supply chain:** osv-scanner for vulnerabilities — never Trivy (tag-hijack, GHSA-69fq-xp46-6x23). Pin every GitHub Action by commit digest, not tag. Checksum-verify every binary downloaded in CI. Pin the model by digest (`ollama pull model@sha256:…`), record it in the SBOM. `uv sync --frozen` everywhere; CI fails on a stale lockfile.
8. **Executable claims must be executed.** A check verified by reading code is INFERRED. Only a run makes it CONFIRMED.
9. **Terse output.** Findings over narration. No hyperbole.

# Phase 0 — Preflight & ingest (read-only, then verify)

- **Toolchain preflight.** Verify on this host, recording versions: Godot 4.7.1 (`godot --version`), Python 3.11+, uv, CMake + a C++17 compiler, Ollama (`ollama --version`, `GET /api/tags`), git. Each missing or wrong-version tool is a P0 in AUDIT.md before any planning.
- **Sandbox preflight.** Run the actual sandbox smoke test: `bwrap --unshare-user --ro-bind / / --proc /proc --dev /dev true`. If it fails (EPERM on user namespaces, AppArmor restriction), record it, check `sysctl kernel.unprivileged_userns_clone` and `/proc/sys/kernel/apparmor_restrict_unprivileged_userns`, and flag decision D-05 to the human with the evidence. Never let the sandbox degrade silently.
- **Hardware envelope.** Inventory GPU(s), VRAM, RAM. Record against the kit's model table (Qwen2.5-VL-7B ≈ 6–8 GB at Q4; Gemma 3 12B ≈ 8–12 GB). State the measured floor in AUDIT.md; if the host is below it, that is a P0 for the agent milestones, not a surprise at M5.
- **CI command dry-run.** Execute every command the §7.2 workflow will run, locally, before relying on it: `godot --headless --check-only --script` on each addon file (with a timeout wrapper); the gdUnit4 invocation against the demo project including the `--import` pass a fresh checkout needs; `uv lock --check`. Fix the workflow where reality disagrees.
- **Ingest.** Read the kit, the audit outputs, and the repo. List every amendment A-## and its dependency order. List every open decision D-01…D-08: answered, or default adopted — record which, explicitly. D-04 (build the layer in v1?) and D-05 (sandbox mechanism) block milestone planning; get human answers now if not already answered.
- **Compressed audit (only if no v3.0 audit exists).** Run Phases 0–4 of the audit prompt against the kit and repo. Produce AUDIT.md. Do not skip this to "save time"; building an unaudited design is how F-001-class bugs ship.

# Phase 1 — Research (read-only)

- Map the repo: stack per plane (addon / layer / operator / UI), entry points, build/run/test commands, and every user-facing flow (install → launch → first flow → first approval → report).
- Build and run it. Document actual behaviour per flow against the kit's intended behaviour.
- **Re-verify the time-sensitive claims as of today** (the audit's Annex B schedule): current Godot stable and the 4.8 policy; issue #100004 status; EditorInterface and WebSocketPeer API surface; Ollama structured-outputs behaviour on the pinned version; every §4.3 model's licence, lineage, and current Ollama tag; tool versions (uv, osv-scanner, gitleaks, gdUnit4, gdtoolkit); Chrome LNA enforcement state. Anything changed since the kit was dated is a finding, and if any of the three architectural load-bearers changed, STOP and report before writing another line.
- Verify current best practice for each stack component against primary sources; flag anything the kit or repo does that is deprecated or known-vulnerable.
- Write AUDIT.md: findings P0 (security/broken) / P1 (correctness/UX) / P2 (polish), each with file:line and evidence, cross-referenced to kit F-### and audit F-1## where overlapping.

# Phase 2 — Plan

Write PLAN.md:
- Ordered work mapped to: kit milestones M0–M6 (M7 only with explicit approval per D-04), kit findings F-001…F-030, audit findings F-1## and amendments A-##, and the audit's seeded suspects S-01…S-16 (each gets a disposition: fixed, verified-clear, or deferred with reason).
- Acceptance criteria per item, testable by execution.
- Explicit non-goals (the kit's Part 8 non-goals, verbatim, plus anything the audit added).
Then proceed — no approval gate except: Rule 9 triggers, any change to a §6 security gate, starting M7, or adopting a model not in the kit's §4.3 pass-list.

# Phase 3 — Implement

Work PLAN.md in priority order. One logical change per commit; messages reference the finding or amendment ID. No scope creep.
Code standards per plane: GDScript fully typed, gdlint/gdformat clean; Python `mypy --strict`, ruff clean; C++ `-Wall -Wextra -Werror`, no implicit-layer code paths; web UI — no third-party origins, vendored assets, CSP set.
Every document describing code carries the provenance front matter (`sources:`, `verified:`) per kit §7.4.
The model is a client of the flow runner, never a component of it: the runner must pass its whole suite with the model disabled.

# Phase 4 — Verification loop

Repeat:
1. Build from clean state (fresh clone or equivalent).
2. Run every gate in the CI gate spec locally: format, lint, parse, types, unit tests, contract tests, vendor gate, licence gate, bind gate, implicit-layer gate, secrets, SBOM, osv-scanner.
3. Run every flow in `flows/` end to end, model-disabled, then model-enabled. Log pass/fail per flow in VERIFICATION.md with evidence — and for every step record the capture tier actually used, the injection tier, and the settle outcome. A run whose steps are all TIMEOUT_PROCEED is not a passing run; it is a run that is not synchronising. Say so.
4. Security spot-checks by execution, every loop: unauthenticated engine connection closes; wrong protocol version closes clearly; a mutating action without approval cannot execute (attempt it); a path-traversal write is rejected and logged; the UI rejects a bad Origin; `grep -rn "0\.0\.0\.0"` over `operator/ addon/` is empty.
5. Fix failures.

Exit when every Definition of Done item passes on **two consecutive full runs** — **three** for the flow/smoke and XR-timing surfaces, which are flaky-async by nature. If the same failure survives three fix attempts, stop and write BLOCKERS.md with root-cause analysis instead of thrashing.

# Definition of Done

The kit's Part 8 Definition of Done applies verbatim. In addition, and replacing its web-generic items with plane-specific ones:

- Fresh clone builds and runs with the documented commands on the stated minimum hardware; the measured resource envelope (GPU/VRAM/RAM floor, per-step latency) is documented in README and was actually measured, not estimated.
- Zero lint, type, parse, or compiler-warning errors, or documented suppressions with justification. Godot CLI checks ran under a timeout; no CI step can hang in the debugger.
- Every flow in `flows/` completes end to end with no unhandled exception and no engine debugger errors, with per-step tier and settle evidence in the run bundle.
- The approval gate is proven unbypassable by execution: no mutating action path exists that skips it, and the audit log records the attempt when one is tried.
- Audit log is tamper-evident by the mechanism the audit amendment specifies (hash-chained or signed); "append-only" as an unenforced intention does not count.
- Model weights pinned by digest and recorded in the SBOM; all GitHub Actions pinned by commit digest; all CI-downloaded binaries checksum-verified.
- Sandbox preflight is part of the operator CLI startup; if the sandbox is unavailable the agent refuses to run mutating flows and says why.
- Security: osv-scanner clean or accepted risks in `osv-scanner.toml` with reason and expiry; full git history scanned for secrets; token file created with the most restrictive permissions the platform allows, and the claim in the docs matches the code.
- Web UI: loopback bind, Origin allowlist, token gate, vendored assets, CSP with no third-party origins, loading/empty/error states, keyboard-navigable, visible focus, WCAG 2.2 AA baseline pass — verified with the network cable unplugged.
- Docs: README (setup, build, run, tier model, hardware floor, troubleshooting), CHANGELOG (v1.0 → v2.0 → production deltas), SHIP.md. Every document describing code has current provenance front matter.

# Human stop points (hard)

Stop and wait for explicit human decision before: starting M7 (D-04); changing any §6 security gate or its CI enforcement; adopting any model not on the kit's pass-list; any Rule 9 action; shipping with any D-decision still on an unexamined default.

# Final report

SHIP.md: what changed; what was tested with evidence (every claim CONFIRMED-by-execution or marked UNTESTED); known limitations; residual risks; install and run steps. Include three tables: the kit's F-001…F-030 with disposition; the audit's F-1##/S-01…S-16 with disposition; the amendments A-## applied, in the order applied. Close with the resource envelope as measured.

---

## Footnotes

[^1^]: https://docs.godotengine.org/en/latest/tutorials/editor/command_line_tutorial.html — `--check-only` parses errors only, requires `--script`; `--headless` required on display-less platforms.
[^2^]: https://forum.godotengine.org/t/cli-showing-gdscript-warnings/132160 — warnings require `--debug`; debugger hang workaround via timeout (Jan 2026).
[^3^]: https://github.com/godot-gdunit-labs/gdUnit4 — CLI tool, JUnit/HTML reports, GitHub Action; compatibility table (4.7.x requires ≥ v6.2.0).
[^4^]: https://godotengine.org/asset-library/asset/4390 — gdUnit4 v6.2.0 asset page (retrieved 9 Aug 2026).
[^5^]: https://github.com/containers/bubblewrap — user-namespace dependency; security policy lives in bwrap arguments; setuid mode removed.
[^6^]: https://forum.cursor.com/t/agent-cli-linux-sandbox-preflight-fails-unshare-eperm-unless-run-under-strace-apparmor-restrict-unprivileged-userns-1/160039 — reproduced EPERM preflight failure with `apparmor_restrict_unprivileged_userns=1` (May 2026).
[^7^]: https://meshworld.in/blog/cheatsheets/uv-cheatsheet/ — `uv sync --frozen` as the CI command; `uv lock --check` for stale lockfiles (2026).
[^8^]: https://godotengine.org/article/maintenance-release-godot-4-7-1/ — Godot 4.7.1 maintenance release, 14 Jul 2026.
