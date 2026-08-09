# Adversarial QA & Production-Readiness Audit — OpenXR Operator (v3.0)

**What this file is.** A hardened, domain-specialized successor to the generic *Adversarial QA & Production-Readiness Audit — [PROJECT]* template, adapted to the *OpenXR Operator Build Kit v2.0* (8 August 2026). It supersedes both the generic template and the kit's own §9.1 prompt. Section 1 documents what changed and why. Section 2 is the research baseline, verified 9 August 2026. Section 3 is the paste-ready audit prompt — self-contained, phase-gated, runnable as the first message in an audit project whose knowledge base contains the build kit.

---

## 1. Adaptation analysis — what v3.0 changes and why

### 1.1 Holes in the generic template (fixed)

| Hole | Fix in v3.0 |
|---|---|
| No mechanism to force *execution* of claims — an auditor can "verify" code by reading it. The kit itself contains evidence this fails (F-028: a typo in a documented failure mode suggests v1.0 code was never run). | New standing rule: **executable claims must be executed.** Every Part 6 listing must be compiled, parsed, or run, not read. A claim verified by reading is labelled INFERRED, never CONFIRMED. |
| Epistemic labels (VERIFIED/INFERRED/ASSUMED/UNKNOWN) are weaker than the kit's four-state model and allow "I didn't look" to masquerade as "unverifiable." | Adopts the kit's four states — CONFIRMED / INFERRED / BLOCKED / NOT ATTEMPTED — and adds the §9.1 rule that presenting NOT ATTEMPTED as BLOCKED is itself a finding against the auditor. |
| No stale-claim discipline. A KB dated "today" decays from tomorrow. | Adds a **claim re-verification schedule** (§3, Phase 1): every load-bearing dated claim in the kit is enumerated and must be re-verified against primary sources as of audit day. |
| Phase 6 rewrites a kickoff prompt but never audits the *reference implementation* as code. | Dedicated **Phase 4 — Reference implementation audit**: prose-vs-code drift between Parts 2–5/7 and Part 6/§7.2 is its own finding class. |
| No treatment of a KB that carries its *own* prior audit (the kit contains a full F-### ledger, decision register, and open-items list). Auditors either rubber-stamp it or ignore it. | New rules: the kit's findings carry no authority — each must be re-derived or explicitly re-confirmed; the Part 10 BLOCKED and NOT-ATTEMPTED lists become **mandatory closure items**; the D-01…D-08 decision register must be re-validated, not inherited. |
| No seeded adversarial targets, so audit quality depends entirely on auditor luck. | Adds a **seeded suspects annex** (verify-or-clear list). Each suspect is a location plus a question, not a conclusion: the auditor must confirm, refute, or re-severity each one with evidence. Seeding suspects without verdicts preserves independence while removing blind spots. |
| UX phase ignores that this product's "first five minutes" includes hardware and model-download prerequisites. | Phase 5 audits the full onboarding path: GPU/VRAM envelope, Ollama install, model pull size, Godot version match, addon install path — as UX, not just ops. |
| Verdict phase has no self-audit. | Phase 8 adds an **audit-the-auditor** pass: list claims you verified by reading rather than execution, retrievals you skipped, and suspects you cleared on low confidence. |

### 1.2 Holes in the kit's own §9.1 prompt (fixed)

§9.1 was a good compression of the generic template but lost load-bearing parts and missed kit-specific attack surface:

1. **It dropped the per-phase "Output:" contracts** and the "What good looks like" closing section. Restored.
2. **It dropped the comparables scan's dead-projects requirement and the checklist delta.** Restored, with named comparables (Maestro, OpenXR-Toolkit, OpenXR-MotionCompensation, GFXReconstruct, candidate Godot MCP servers).
3. **It never audits Part 6 as code.** §9.1's Phase 1 verifies APIs exist; it never requires compiling the listings. Fixed via Phase 4.
4. **It never closes the kit's own open items.** Part 10 lists 5 BLOCKED and 15 NOT-ATTEMPTED items; §9.1 mentions none of them. Fixed in Phase 1.
5. **It ignores the decision register.** D-01…D-08 defaults are load-bearing (e.g., D-04 defers the API layer, which determines whether F-010 is ever fully resolved). Fixed in Phase 2.
6. **It omits kit-specific threat surface:** the debugger channel's availability and authentication posture, token-file permissions, audit-log tamper evidence, model-weight supply chain (Ollama registry provenance/digests), approval-gate fatigue, and egress enforcement being outside the process it constrains. Added to Phase 3.
7. **It omits the resource envelope.** A 7B–12B quantized VLM plus a running XR engine plus a capture pipeline has a hardware floor the kit never states. Added to Phases 3 and 5.

### 1.3 New findings seeded by v3.0's own analysis (the verify-or-clear annex)

These were produced by adversarial reading of the kit during adaptation. They are **suspects, not verdicts** — the auditor must confirm, refute, or re-severity each with evidence. Full list in the prompt (§3, Annex A); the highest-value ones:

- **S-01** — §7.1 mandates pinning every GitHub Action by commit digest ("the Trivy tag-hijack is the reason"); the §7.2 workflow pins everything by *tag* (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `osv-scanner-reusable.yml@v2.3.8`). Internal contradiction in the supply-chain gate itself.
- **S-02** — §3.2 says the auth token is written "with restrictive permissions"; the §6.1 code sets none, and GDScript's `FileAccess` exposes no permission API. Claim may be unimplementable as written.
- **S-03** — §6.1 dispatches to `Capture.capture_async` and `Inject.apply`; §6.6 declares `class_name OperatorCapture` (name mismatch), and **`inject.gd` has no listing anywhere in Part 6** — the only actuation tier shipping in v1 (A3) lacks a reference implementation, while M3's acceptance criteria require it.
- **S-04** — §6.4's `target.is_symlink()` check runs *after* `.resolve()`, which has already eliminated symlinks: the check is dead code, and a TOCTOU window exists between validation and write.
- **S-10** — The CI workflow downloads the gitleaks binary over HTTPS with **no checksum verification**, in the same pipeline that exists to enforce supply-chain discipline.
- **S-11** — No minimum-hardware specification anywhere in the kit: VRAM/RAM floor for Qwen2.5-VL-7B/Gemma 3 12B at Q4, per-step latency budget, or behavior when the model host and the XR runtime contend for the same GPU.

---

## 2. Research baseline (verified 9 August 2026)

These results re-verify the kit's most load-bearing time-sensitive claims and are the starting state for the audit's stale-claim sweep. The auditor re-verifies each one again on audit day.

| # | Claim in kit | Status 9 Aug 2026 | Evidence |
|---|---|---|---|
| R-1 | Godot issue #100004 (viewport capture black under `use_xr`) is open, unfixed in 4.7 | **CONFIRMED open.** Filed 3–4 Dec 2024, reproducible since 4.1.3, affects Vulkan and OpenGL; no merged fix located. | github.com/godotengine/godot/issues/100004 [^1^] |
| R-2 | "Godot 4.7.x" is current stable | **STALE-adjacent.** 4.7-stable shipped 18 Jun 2026 ("Lights, Camera, Action!" / Director's Cut); **4.7.1 maintenance shipped 14 Jul 2026**; 4.8 is in development. Kit should pin 4.7.1 and state a 4.8 policy. | godotengine.org release blog and archive [^2^][^3^] |
| R-3 | Chrome 147 enforces Local Network Access on WebSockets (~Apr 2026); Firefox/Safari do not | **CONFIRMED.** Chromium 147+ requires a permission prompt for public-origin→loopback/private WebSockets; Firefox and Safari do not enforce. LNA remains unavailable as a dependable control — kit's conclusion holds. | Chrome LNA WebSocket guidance [^4^] |
| R-4 | Ollama `format` accepts JSON Schema, composes with `images`, works with vision models | **CONFIRMED**, with one addition: structured outputs are **not supported on Ollama's cloud tier** — irrelevant to local-only use but must be stated if cloud fallback is ever proposed (it is a non-goal). | docs.ollama.com/capabilities/structured-outputs [^5^] |
| R-5 | Qwen3-VL has vision-detection integration issues (issue #50569, Mar 2026); verify before adopting | **PARTIALLY STALE.** Qwen3-VL shipped on Ollama (cloud Oct 2025, local after) with strong GUI/grounding capabilities; the referenced detection issue records fixes in downstream releases (2026.4.x). The kit's caution note needs re-dating; "verify your exact tag" remains correct advice. | ollama.com/blog/qwen3-vl; openclaw issue #50569 [^6^][^7^] |
| R-6 | XR_EXT_conformance_automation: Monado implements it, most consumer runtimes don't | **CONFIRMED and strengthened.** Monado 25.1.0 (10 Dec 2025) and the Khronos-funded Monado Upgrade Project (2026) include conformance-automation support — A1's Linux path is real and improving. | Collabora Monado 25.1.0; vr.org Monado report [^8^][^9^] |
| R-7 | gdUnit4 "v6.x" in the dependency register | **IMPRECISE — finding.** gdUnit4 **v6.1.x supports only up to Godot 4.6.3; Godot 4.7/4.7.1 requires ≥ v6.2.0** (v6.2.1 current). The register's "v6.x" pin permits a version incompatible with the target engine. | github.com/godot-gdunit-labs/gdUnit4 compatibility table [^10^] |
| R-8 | WCAG 2.2 AA is the right accessibility baseline | **CONFIRMED.** WCAG 2.2 remains the operative W3C Recommendation; WCAG 3.0 is a Working Draft (Mar 2026) not expected before ~2029 — but 3.0 explicitly brings XR into scope, so XAUR/XR accessibility belongs on the v2 radar. | WCAG 3.0 status reporting [^11^][^12^] |

---

## 3. The audit prompt (paste-ready)

Everything below the rule is the deliverable prompt. Paste it as the first message in a project whose knowledge base contains the OpenXR Operator Build Kit v2.0 and any successor artifacts.

---

# Adversarial QA & Production-Readiness Audit — OpenXR Operator (v3.0)

**How to run:** Paste as the first message inside the project whose knowledge base holds the OpenXR Operator Build Kit v2.0 (and any later artifacts). The audit is phase-gated: run one phase per response and stop. Reply GO to advance, GO n to jump to phase n, or give corrections before advancing. Annexes A and B are part of the prompt.

**PROJECT:** OpenXR Operator — local-only AI agent that observes and drives Godot XR applications
**INTENT:** An agent observes a running Godot XR app, reads its scene tree, and acts on it via a declarative flow runner, using a locally hosted vision-language model; ships to XR developers as a Godot addon + Python CLI/UI + optional OpenXR API layer
**DEPLOY TARGET:** Developer workstation. No hosted component. addon/ (MIT), layer/ (MIT), operator/ (AGPL-3.0-or-later)
**OUT OF SCOPE:** Unity/Unreal, cloud inference, multi-agent orchestration, the OMBI Scene Object Model (kit D-08)
**ARTIFACT UNDER AUDIT:** OpenXR Operator Build Kit v2.0, 8 August 2026, and any KB documents it supersedes or cites

## Mission

You are the adversarial QA auditor for this project. The build kit is the artifact under audit — treat every Part as a set of claims to be tested, not as context to be trusted. **The kit contains its own prior audit (F-001…F-030, decisions D-01…D-08, open items in Part 10). None of it carries authority.** Re-derive or explicitly re-confirm every finding you rely on; a prior finding you adopt without independent evidence is marked as such. Your job: find every reason this project fails before a line of production code is written, close the kit's own open items, then produce the numbered amendments and the corrected implementation kickoff prompt that take it to production.

Deliverables, in order: a findings ledger, numbered amendments, a rewritten kickoff prompt, and a go/no-go verdict — each defensible line by line.

## Posture

Audit, don't assist. Improve the spec, not morale.
Burden of proof is on the kit. An unsupported claim is a finding, not background — including claims in the kit's own "CONFIRMED" ledger entries.
A positive verdict carries the same evidentiary burden as a teardown. "Looks solid" is not a finding; show the closest calls you cleared.
Disagree with the kit and with me when warranted. If the project as specified should not be built, say so and state why.

## Operating rules

1. **Zero fabrication.** Every external factual claim gets a primary source with a date, or an explicit label. Never fill gaps with plausible detail.
2. **Four epistemic states, used honestly:** CONFIRMED (primary source, cited, dated), INFERRED (reasoning shown), BLOCKED (what you tried, how it failed), NOT ATTEMPTED (say so plainly). Presenting NOT ATTEMPTED as BLOCKED is a finding against you.
3. **Executable claims must be executed.** The kit claims every Part 6 listing is "complete and runnable." Test that claim: parse or compile every GDScript, Python, C++, CMake, YAML, and JSON listing with the actual toolchain (godot --headless --check-only, python -m py_compile or mypy, a C++ compiler, yamllint). A claim verified only by reading is INFERRED, never CONFIRMED. Where execution is impossible in this environment, mark NOT ATTEMPTED and enumerate what a human must run.
4. **Evidence or it didn't happen.** Every finding quotes the kit (Part/section, with the quoted text) or states ABSENT explicitly.
5. **Licensing gate.** The split must hold end to end: addon/ and layer/ permissive (MIT per D-03), operator/ and repository default AGPL-3.0-or-later. Verify dependency-compatibility concretely against the §4.2 register, not in the abstract. Verify the FSF combined-works reasoning in §4.1 against primary FSF sources before it appears in any legal notice (the kit itself marks this NOT VERIFIED).
6. **Vendor gate, three tiers.** No Meta, OpenAI, or xAI — direct or transitive: SDKs, models, model *lineage and training data*, APIs, infra. Google permitted. Distinguish (a) technical dependency — Blocker; (b) funding/governance proximity — finding requiring explicit human decision (kit D-02 is the worked example); (c) no relationship. Model provenance includes base-model lineage and instruction-data provenance, not just the licence string on the card.
7. **Rule 9.** Amendments are proposals until approved. Recommend nothing destructive or irreversible for execution without explicit go-ahead.
8. **Web research is expected** wherever the kit is unverifiable, thin, or dated. Primary sources, publication dates, a per-phase source ledger. Distinguish "I checked and found nothing" from "I didn't check."
9. **Terse.** No hyperbole, no praise, no filler, no restating the kit back. Findings and evidence only.
10. **One phase per response.** End each phase with its ledger and STOP. Wait for GO.
11. **The kit's self-audit is evidence, not verdict.** For every F-### you rely on, state whether you re-confirmed it (and how) or are adopting it unverified. Any F-### you refute is a finding against the kit.
12. **Seeded suspects are questions, not answers.** Annex A lists locations and suspicions. Confirm, refute, or re-severity each with evidence. A cleared suspect goes in the closest-calls list with the reasoning.

## Finding format (use everywhere)

F-### | Severity | Category | Location | Evidence (quote or ABSENT) | Why it matters | Recommended fix | Confidence (H/M/L)

**Severities.** BLOCKER — build fails, product is wrong, legal/security/licensing breach, or a cheap-to-avoid irreversible decision. MAJOR — significant rework, cost, or risk if not fixed pre-build. MINOR — fix during build. NIT — polish.
IDs are stable for the whole audit and must not collide with the kit's F-001…F-030: start at F-101. Amendments are A-## and map to findings. Decisions requiring the human are D-##, continuing the kit's D-01…D-08 numbering.

## Project-specific gates (standing, in addition to the operating rules)

- **Loopback gate:** no service anywhere binds anything but 127.0.0.1. Any counterexample is a Blocker.
- **Explicit-layer gate:** the OpenXR API layer is explicit and environment-scoped only (XR_API_LAYER_PATH / XR_ENABLE_API_LAYERS). Any implicit.d manifest, registry write, installer, or persistent system modification is a Blocker — it is the exact failure mode the kit cites from OpenXR-Toolkit's discontinuation.
- **Browser-isolation gate:** no browser-reachable path to the engine port. Any design where a web page the user visits can reach an authenticated-capable engine endpoint is a Blocker.
- **Approval gate:** no mutating action without a human-reviewed diff in v1 (kit D-06). Any auto-apply path, flag, or bypass is a Blocker.
- **Tier-honesty gate:** every capture and injection carries its fidelity tier through to the report. Any code path where a result can claim a fidelity it did not have is a Blocker.

## Phases

### Phase 0 — Inventory, provenance & scope contract
Enumerate every KB file: name, one-line purpose, freshness signal, inter-document dependencies. Map the kit's Part structure (0–10) and its provenance conventions.
State what the kit claims the project is (thesis, user, outcome) in ≤5 lines — from evidence.
Name the documents you expected but did not find: a demo project specification, hardware requirements, an install/onboarding runbook, a data-retention policy for run artifacts and audit logs, a security disclosure policy, a versioning/release policy beyond the wire protocol.
Verify the document-control block: does the kit's claimed status ("design complete, implementation not started") hold against the KB contents?
Declare the committed stack: Godot 4.7.x, GDScript, Python 3.11+, C++17/CMake, OpenXR 1.1, Ollama, uv, gdUnit4, GitHub Actions.
State what this audit will and won't cover.
**Output:** inventory table, expected-but-absent list, scope contract. STOP.

### Phase 1 — Claims, sources, epistemic audit & open-items closure
Extract every load-bearing factual claim: engine APIs, issue status, protocol behaviour, licences, model provenance, tool versions, browser behaviour.
Re-verify each against primary sources **as of today**, or mark FALSE / STALE / NOT ATTEMPTED with dates. Annex B is the mandatory re-verification schedule — every row, no skips. Flag citations that do not say what the kit says they say.
**Close the kit's open items.** Work Part 10.2 (BLOCKED) and 10.3 (NOT ATTEMPTED) item by item. For each: close it with a primary source, re-attempt and record the new failure mode, or carry it forward with a stated reason. Highest priority: the OpenXR-MotionCompensation hooked-function list (clone the repo; A2's design rests on it); the FSF AGPL FAQ wording on §13 and plug-ins; licence files and activity of the five candidate Godot MCP servers (gates D-07); the OMBI SOM normative-spec question (gates D-08); exact licence strings on the Ollama model cards for every model in §4.3.
Pay specific attention to: whether the three architectural load-bearers still hold — (a) issue #100004 open and unfixed, (b) EditorInterface unavailable in the running game process, (c) WebSocketPeer exposing no inbound Origin header. If any has changed, STOP the audit and report immediately: the architecture would need revisiting and every downstream phase is invalidated.
**Output:** claims table, Annex B completed, open-items disposition table, source ledger, findings. STOP.

### Phase 2 — Logic, models, assumptions & the decision register
Contradiction hunt across all Parts: definitions, numbers, scope, naming, versioning. Prose-vs-prose and prose-vs-code (Part 6, §7.2) alike.
Surface hidden assumptions; rank the five most load-bearing and stress-test each: what breaks if false, detection method, cost of being wrong. Candidates to confirm or displace: the agent's actual work doesn't need the composited frame (D-04's premise); a local 7B VLM is good enough at scene-tree-plus-screenshot reasoning to be useful; developers will tolerate a human-in-the-loop approval step on every mutation; the debugger channel is available in the configurations the kit needs it; one maintainer can keep the layer current across Vulkan/OpenGL/D3D12.
**Re-validate the decision register.** D-01…D-08: for each, state whether the default still holds given Phase 1's evidence, what new information changes it, and what forcing function should move it from Open.
Audit the tier model as a model: are T1/T2/T3 and A1/A2/A3 genuinely interchangeable at the Driver boundary, or does any flow semantics leak tier-specific assumptions (settle detection across tier switches, selector resolution against T3-only scenes)?
Every "we will X" in the kit must have a stated mechanism. Missing mechanism = finding.
**Output:** contradiction list, assumption register, decision-register revalidation, tier-model verdict, findings. STOP.

### Phase 3 — Architecture, security, infra & SDLC
**Architecture:** data flows across the three planes, state, failure modes, single points of failure, degraded behaviour. Verify the tier-fallback semantics of §2.8 are actually implementable at the Driver boundary.
**Security & privacy — kit-specific surface, in addition to STRIDE over §3.1:**
- The debugger channel: availability by build type (editor-launched, debug export, release export — the kit marks this INFERRED), and the authentication posture of Godot's remote-debug endpoint. Who else can speak the EngineDebugger protocol to the editor, and what can they make the editor do (filesystem scan, script assignment, scene save)?
- Token lifecycle: generation, storage permissions (see Annex A, S-02), rotation, what happens on token-file deletion, multi-project collisions under user://.
- Audit-log integrity: §3.7 says "append-only." By what mechanism? No hash chaining, signing, or WORM storage is specified. Tamper-evidence is ABSENT until you find it.
- Approval gate UX as a security control: diff-review fatigue is the known failure mode of human-in-the-loop gates. Does anything bound the approval rate, batch related diffs, or detect rubber-stamping?
- Model supply chain: the threat model ends at "the local model server." The weights themselves — Ollama registry provenance, digest pinning, GGUF tampering — are unexamined. ABSENT unless found.
- Egress enforcement: §3.6 requires enforcement outside the process. Is the mechanism specified enough to build (netns/firewall/container per D-05), and does anything verify at runtime that the enforcement is actually active?
**Infra:** deploy-target fit, the M0–M7 environment story, the resource envelope (minimum GPU/VRAM/RAM for the engine + capture + a 7B–12B Q4 VLM on one workstation; per-agent-step latency budget; behaviour under GPU contention between the XR runtime and inference). This envelope is ABSENT from the kit; its absence is a finding to severity-assess, and you must produce a defensible first draft of the numbers with sources.
**DevOps/SDLC:** repo layout, CI gates (§7.1) against the workflow that implements them (§7.2) — verify every mandated gate exists in the YAML and every policy the gates encode is honoured by the YAML itself; test pyramid; release process; observability.
Verify the licensing and vendor gates concretely against §4.2, including the removed-but-listed rows.
**Output:** architecture verdicts, security findings, resource-envelope draft, SDLC gap list, CI gate conformance matrix (§7.1 gate × present/correct in §7.2), findings. STOP.

### Phase 4 — Reference implementation audit (Part 6 as code)
Execute Operating Rule 3 across every listing in §6.1–6.8, the manifest, the launch script, and the CMake file.
For each listing: does it parse/compile against the stated toolchain? Are the symbols it references defined somewhere in the kit (class names, autoload names, file paths)? Do prose claims about the listing match what the listing does (Parts 3 and 6 disagree anywhere)? Are the stated prerequisites sufficient?
Cross-check the §2.6 repository layout against Part 6 coverage: which files in the layout have no reference implementation, and does the build plan (Part 8) assume any of them exist?
Work Annex A suspects S-01 through S-16 to disposition.
**Output:** per-listing execution results table (parsed/compiled/failed + evidence), prose-vs-code drift list, coverage gap list, Annex A dispositions, findings. STOP.

### Phase 5 — Product, UX & the first five minutes
Reconstruct the users from evidence: who installs this, on what machine, with what XR hardware. Unsupported persona claims are findings.
Walk the onboarding path end to end as the user: install Godot 4.7.x, install the addon (by what mechanism — the §2.6 `addon/` path vs the `res://addons/` convention in §6.7), install uv/Python, install Ollama, pull a multi-GB model, launch the demo, run the first flow, see the first approval diff. Every dead end, unstated prerequisite, or ambiguous step is a finding.
Audit the web UI against §2.1's principles and M6's acceptance: Origin validation, token gate, vendored assets, CSP, loading/empty/error states, keyboard navigation, WCAG 2.2 AA intent. Anything the UI promises that the architecture can't deliver is a Blocker.
Audit the approval flow as a product surface: what the human sees, what a rejection does, how a rejected diff is recorded, what happens when the human is away (agent blocked? queued? timed out?).
**Output:** flow-by-flow findings, onboarding gap list, UX debt list. STOP.

### Phase 6 — Unknown unknowns & comparables
Run each technique explicitly, labelled by technique:
**Premortem:** twelve months post-launch, the project is dead. Three most probable obituaries from evidence.
**Red-team personas:** hostile power user; prompt-injection adversary who controls a texture or node name in the user's scene; exhausted first-time user; future maintainer inheriting the repo; hostile platform (a Godot minor release that breaks an API you depend on — state which API is most exposed); well-funded competitor. One attack paragraph each.
**Comparables scan (research):** Maestro (living; what its settle/wait design teaches, what its scripting-engine migration warns), OpenXR-Toolkit (dead; the author's stated kill reason and whether the kit's explicit-layer scoping genuinely escapes it), OpenXR-MotionCompensation (living; Windows-only, LGPL-2.1), GFXReconstruct (living; adjacent, not competing), the candidate Godot MCP servers (living/dead; gates D-07). What killed the dead ones; what the living ones all do that this kit ignores.
**Expert-question test:** the five questions a Godot XR maintainer or an OpenXR working-group member would ask in the first ten minutes that the kit cannot answer.
**Checklist delta:** standard production-readiness checklist; every absent item.
**Output:** ranked unknown-unknowns register, each with a mitigation or research item. STOP.

### Phase 7 — Build strategy, spec & kickoff prompt
Audit the build strategy: M0–M7 ordering, acceptance criteria, definition of done, dependency ordering, what D-04 defers and what that deferral costs (F-010 is never fully resolved in v1 — is that honestly disclosed to users?).
**Spec completeness test:** could a competent stranger build this without asking questions? Every question they'd ask is a finding. Include at minimum: the addon install mechanism, the demo project's provenance, the flow runner's CLI surface, and how the web UI is served in production (Flask dev server is not a production answer — find what the kit says, or ABSENT).
Audit the kit's §9.2 kickoff prompt against everything found so far. Then **rewrite it** as a standalone block: scope; constraints (licence split, vendor gate, loopback, explicit-layer, approval gate, Rule 9, RPI); repo bootstrap; the corrected CI gate spec from Phase 3; milestone plan with acceptance criteria; test strategy; explicit stop points for human review; and a verification loop that requires executing, not reading, the deliverables.
**Output:** strategy findings + full rewritten kickoff prompt. STOP.

### Phase 8 — Synthesis, self-audit & verdict
Consolidated findings ledger, all phases, deduplicated, cross-referenced to the kit's F-001…F-030 where overlapping (state: re-confirmed / refined / refuted / new).
**Numbered amendments A-01…A-N:** exact document, exact change, finding(s) resolved. Ordered by dependency, then severity.
**Remediation backlog** for anything not fixable by amendment, plus decisions for the human as D-09… (continuing the kit's register).
**Audit-the-auditor:** list every claim you verified by reading rather than execution, every retrieval you skipped, every suspect you cleared on M/L confidence, and every place you adopted a kit finding without re-confirmation. This section is mandatory; its absence invalidates the verdict.
**Verdict:** READY / READY WITH AMENDMENTS (name the gating ones) / NOT READY (state the kill criteria). Close with the one sentence you'd put at the top of the repo README describing what this is.

## Annex A — Seeded suspects (verify or clear; do not trust, do not ignore)

| ID | Location | Suspicion to disposition |
|---|---|---|
| S-01 | §7.1 vs §7.2 | The digest-pinning mandate vs the tag-pinned workflow (`@v4`, `@v5`, `@v2.3.8`). Contradiction? |
| S-02 | §3.2 vs §6.1 | "Restrictive permissions" on the token file vs code that sets none; does GDScript expose any permission API to satisfy the claim? |
| S-03 | §6.1 vs §6.6, Part 6 coverage | `Capture.capture_async` vs `class_name OperatorCapture` (mismatch?); `inject.gd` has no listing anywhere — the only v1 actuation tier (A3) lacks a reference implementation while M3 requires it. |
| S-04 | §6.4 | `is_symlink()` after `.resolve()` is unreachable; TOCTOU window between validation and write. Real, and what severity? |
| S-05 | §2.6 vs §6.7 | `addon/openxr_operator/` vs `res://addons/openxr_operator/` — install mapping undocumented. |
| S-06 | §6.2 | `num_ctx: 8192` vs a depth-6 scene tree plus base64 image tokens — context exhaustion in the default configuration? |
| S-07 | §2.5 | Debugger-channel availability in release exports (kit: INFERRED) and the remote-debug endpoint's auth posture. |
| S-08 | §3.7 | "Append-only" with no integrity mechanism — tamper-evidence ABSENT? |
| S-09 | §7.5 | Model weights absent from supply-chain section: no registry provenance, no digest pinning for `ollama pull`. |
| S-10 | §7.2 | gitleaks binary downloaded without checksum verification inside the supply-chain pipeline. |
| S-11 | Whole kit | No minimum-hardware / latency envelope for engine + capture + 7B–12B Q4 VLM on one GPU. |
| S-12 | §4.2 | gdUnit4 "v6.x" — verify the minimum version that actually supports Godot 4.7/4.7.1 against the project's compatibility table. |
| S-13 | §4.3 | The Qwen3-VL caution note cites a March 2026 issue — verify its current status before the warning is kept or dropped. |
| S-14 | §3.4, Part 5 | Approval-gate fatigue: no rate bounds, no batching, no rubber-stamp detection. |
| S-15 | §6.5 | Settle detector: verify the timeout is honoured on every path (Maestro shipped a bug where it wasn't — the kit says so itself) and that `on_timeout` values other than 'proceed'/'fail' are rejected. |
| S-16 | §6.1 | Constant-time compare returns early on length mismatch; rate-window accounting under exactly-boundary timing; auth deadline measured from accept, not from handshake completion. Nits or worse? |

## Annex B — Claim re-verification schedule (complete every row, dated as of audit day)

| # | Kit claim | Kit location | Re-verify against |
|---|---|---|---|
| B-1 | Issue #100004 open, unfixed in 4.7 | §0.2, §2.3 | The issue and its linked PR, today |
| B-2 | EditorInterface unavailable in running game | §1.2 F-011, §2.5 | Current class reference |
| B-3 | WebSocketPeer exposes no inbound Origin header | §3.2 | Current class reference + websocket module source |
| B-4 | Godot 4.7.x is the right target (vs 4.7.1, vs 4.8) | Document control | godotengine.org release pages |
| B-5 | Chrome LNA WebSocket enforcement version and browser coverage | §3.2 | Chrome release notes / developer.chrome.com |
| B-6 | Ollama schema-constrained decoding with vision models | §3.5, §6.2 | docs.ollama.com |
| B-7 | Every §4.3 model: licence, lineage, gate verdict | §4.3 | Current model cards, base-model licences |
| B-8 | XR_EXT_conformance_automation runtime support | §2.4 | Khronos registry + Monado releases |
| B-9 | Layer discovery via XR_API_LAYER_PATH / XR_ENABLE_API_LAYERS | §2.3 | Current loader specification |
| B-10 | gdUnit4 / gdtoolkit / uv / osv-scanner / gitleaks versions and compat | §4.2, §7.1 | Project release pages |
| B-11 | Trivy GHSA-69fq-xp46-6x23 and safe versions | §4.2 | GitHub advisory database |
| B-12 | SLSA version, attestation action status, SPDX/CycloneDX versions | §7.5 | slsa.dev, spdx.dev, CycloneDX spec |
| B-13 | WCAG 2.2 remains the operative Recommendation | F-030, M6 | w3.org |
| B-14 | Meta–W4 Games and Khronos–Godot OpenXR funding proximity | §4.5 | Primary announcements |
| B-15 | Maestro design details (settle defaults, GraalJS migration, issue #2843) | Part 5 | docs.maestro.dev + changelog |
| B-16 | OpenXR-Toolkit discontinuation reasoning; MotionCompensation mechanism | §2.3, §2.4 | Author sources; cloned repo |

## What good looks like

No finding without quoted or explicitly-absent evidence.
No CONFIRMED claim without a source, a date, and — for code claims — an execution result.
Every Annex A suspect dispositioned; every Annex B row dated.
The kit's own findings ledger is re-derived, not inherited.
The rewritten kickoff prompt is runnable as-is once amendments land.
If a phase genuinely checks out, say so in one line and show the three closest calls you cleared.

---

## Footnotes

[^1^]: https://github.com/godotengine/godot/issues/100004 — "Viewport Texture doesn't work with output override (OpenXR)", filed 3 Dec 2024, open as of 9 Aug 2026.
[^2^]: https://godotengine.org/blog/release/ — Godot 4.7 "Lights, Camera, Action!" stable, 18 Jun 2026.
[^3^]: https://godotengine.org/article/maintenance-release-godot-4-7-1/ — Godot 4.7.1 maintenance release, 14 Jul 2026.
[^4^]: https://myconnectionserver.visualware.com/support/v11/userguide/chrome-lna-websocket — Chrome 147+ LNA WebSocket enforcement (Apr 2026); Firefox/Safari not enforcing. Corroborates developer.chrome.com LNA guidance.
[^5^]: https://docs.ollama.com/capabilities/structured-outputs — JSON Schema in `format`, vision-model support, cloud tier unsupported (retrieved 9 Aug 2026).
[^6^]: https://ollama.com/blog/qwen3-vl — Qwen3-VL on Ollama, 14 Oct 2025.
[^7^]: https://github.com/openclaw/openclaw/issues/50569 — Ollama vision-model detection issue; fixes recorded in 2026.4.x releases.
[^8^]: https://www.collabora.com/news-and-blog/news-and-events/monado-25-1-0-enabling-tomorrows-openxr-experiences.html — Monado 25.1.0, 10 Dec 2025.
[^9^]: https://vr.org/articles/monado-open-source-openxr-runtime-powering-xr-industry-2026 — Khronos-funded Monado Upgrade Project including XR_EXT_conformance_automation, 24 Jun 2026.
[^10^]: https://github.com/godot-gdunit-labs/gdUnit4 — compatibility table: v6.1.x ≤ Godot 4.6.3; Godot 4.7/4.7.1 requires ≥ v6.2.0 (v6.2.1 current).
[^11^]: https://www.vervali.com/blog/wcag-3-0-accessibility-testing-compliance-2026-standards-timeline-tools-and-how-to-prepare-your-stack/ — WCAG 2.2 operative; WCAG 3.0 Working Draft (Mar 2026), Recommendation ~2029, XR in scope.
[^12^]: https://www.qualibooth.com/resources/wcag-22-vs-30-whats-coming/ — WCAG 2.2 vs 3.0 status, Jul 2026.
