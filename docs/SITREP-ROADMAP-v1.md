# OpenXR Operator — SITREP, Component Dependencies, and the v1 Production Recipe

Date: 2026-11-05 · Repo: `MartinMontero/OpenXR-Operator` (public) · Companion artifact: interactive floorplan (`docs/floorplan/index.html`)

---

## 1. SITREP — where the project actually is

**What it is.** A local, vendor-clean AI agent for building XR apps in Godot (other engines per D-19). A non-developer describes a change in plain language; the agent observes the running app, proposes each change in plain language, and executes only after the human approves. Inference is local-first (Ollama), no hosted service required, no Meta/OpenAI/xAI artifacts or endpoints.

**Current state: code-complete MVP with the real loop proven once, hardening and packaging left.**

| Area | State | Evidence |
|---|---|---|
| Frozen contracts (wire, Driver, action schema, flow schema, ModelBackend) | Done | All consumers use them |
| Godot addon (auth, limits, capture T2/T3, A3 injection, editor bridge) | Done, executed | gdUnit4 suites green on build host |
| Driver + settle | Done, executed | Fake-engine tests incl. capability-before-dispatch, timeout ±50 ms |
| Selectors + flow parser + runner + artifacts + CLI | Done, executed | Full-stack run YAML→runner→engine→bundle+JUnit |
| Model backends (Ollama, llama.cpp) + vendor gates | Done, executed | 130 tests incl. digest-pin enforcement, denylist hosts, no-fallback |
| Approval gate (D-14) + hash-chained audit log | Done, executed | Plain-language cards; tamper detection tests |
| Agent loop | Done, executed | Approved mutation executes; rejection/capability violation never reaches wire |
| Web UI (loopback, token, Origin, CSP) | Done, executed | Real-HTTP tests; approve executes / reject blocks |
| Real model-in-loop on target hardware | **Proven once** | Label set to STATUS: RED with independent readback; malformed step-2 output retried+aborted correctly |
| Real addon ↔ real driver contract roundtrip | **Not yet run** | The remaining integration proof |
| CI end-to-end green | **Blocked on one workflow edit** | static green; test job needs item 2c + gdUnit4 flags |
| Packaging/launcher, non-developer usability, release artifacts | **Not done** | The v1 production work below |

**Significant incidents already handled:** CI repaired from all-failing to green; external audit (5 P1, 4 P2, 3 P3) remediated with executed evidence; cross-project contamination avoided; UI bugs found by real use (token regeneration, Origin fallback, focus-stealing refresh, Referrer-Policy self-own) all fixed and re-verified.

---

## 2. What each component needs from each other

```text
                 USER (plain-language task + approval)
                          │
                          ▼
                 ┌──────────────────┐
                 │   Browser UI     │  token + Origin + CSP
                 └────────┬─────────┘
                          │ start task / approve / status
                          ▼
                 ┌──────────────────┐
                 │   Agent loop     │  validation → containment → approval → execute → audit
                 └──┬────┬────┬────┬┘
                    │    │    │    │
       observe      │    │    │    └──────────────┐
                    │    │    │                   │
                    ▼    │    ▼                   ▼
             ┌────────┐  │  ┌───────────┐   ┌────────────┐
             │ Driver │  │  │  Model    │   │ Audit log  │
             │+settle │  │  │ backends  │   │(hash chain)│
             └───┬────┘  │  └─────┬─────┘   └────────────┘
                 │       │        │
                 ▼       │        ▼
          ┌──────────┐   │   ┌──────────────┐
          │  Addon   │   │   │ Ollama/local │
          │(in-engine)│  │   │ model server │
          └────┬─────┘   │   └──────────────┘
               │         │
               ▼         │
        ┌─────────────┐  │
        │ Running app │  │
        │(Godot/demo) │  │
        └─────────────┘  │
                         │
              ┌──────────┴───────────┐
              │  Flow runner/artifacts│  (independent of model: deterministic tests)
              └──────────────────────┘
```

| Component | Needs from others | Provides to others |
|---|---|---|
| **Browser UI** | AgentLoop (its decisions queue), UI token, a live engine+backend | Task entry, approval decision, status display |
| **AgentLoop** | Driver (observe+execute), ModelBackend (propose), ApprovalGate (human decision), AuditLog, ArtifactWriter, fsguard (containment) | Executed actions, step records, audit events |
| **Driver (+settle)** | Addon over authenticated WebSocket; verified frames | Observation (frames, trees, properties), execution channel, settle outcomes |
| **Model backends** | Local Ollama (default) or opt-in hosted domain; denylist+lineage tables; digest pin | Schema-constrained action JSON, capability report (constraint mode) |
| **ApprovalGate** | Validated action (already schema+capability checked) | ApprovalRecord (approved/rejected + plain-language diff) |
| **AuditLog** | Every event (observation hashes, approvals, executions) | Tamper-evident history, `verify()`/`head_hash()` |
| **ArtifactWriter** | Frames, trees, step records, model exchanges | Run bundle: manifest, commands.jsonl, frames, trees, junit.xml |
| **FlowRunner** | Driver (no model needed), selectors, flow parser, artifacts | Deterministic flows and their evidence |
| **Addon** | Running Godot app; token file | Authenticated observation/actuation surface, black-frame detection, binding assertions, editor bridge |
| **Demo project** | Addon installed+enabled, game playing | The test target for roundtrip and usability |
| **CI gates** | All source, lockfile, workflows, vendored deps | Release-blocking proof the controls actually fire |
| **Kit/decisions** | Nothing (documentation) | Constraints everyone else must honor (D-01…D-19) |

**The dependency that matters most:** the model is a *client* of the runner, not a component of it. Everything below the UI works with the model disabled — that is why 130 tests can be deterministic, and why the smoke flow in CI needs no model.

---

## 3. Roadmap to v1 production

### Phase 0 — Integration truth (days, not weeks)
1. **Land the ci.yml edit** (item 2c + gdUnit4 flags in one commit): project-context GDScript parse, gdUnit4 flags (`--ignoreHeadlessMode`, `-c`, both `-a` suites, project-relative `-rd`, render suite under `xvfb-run` + Dummy audio).
2. **Run the QA contract roundtrip** (`W2-02-qa-contract-roundtrip`): real addon ↔ real GodotDriver, replaying the W2 exit gate (auth rejection, protocol mismatch, capability rejection leaving nothing on the wire, black-frame error, bogus-tracker raise, settle outcomes).
3. **Re-run the pinned real model-in-loop** with the strong form `--model qwen2.5vl:7b@sha256:<digest>` so the pin enforces in-process (2d closed).
4. **Full board green on GitHub**: static + test + gdUnit4 + flow smoke.

**Exit gate:** CI fully green on main; roundtrip card in `swarm/done/` with executed evidence; SHIP.md updated.

### Phase 1 — Packaging (the non-developer install)
1. **One-command launcher** (`tools/start-openxr-operator.ps1` + `.sh`): checks Godot 4.7.1, uv, Ollama; `uv sync --frozen --project operator`; optionally starts Ollama; optionally starts Godot with the demo; prints and opens the tokenized URL. Fixed `OPENXROP_UI_TOKEN` supported (already in code).
2. **Install docs**: README quickstart already exists; add a 5-minute video/GIF of the actual run (task → approval → label turns red) and a "first five minutes" section for non-developers.
3. **Fresh-clone verification on two machines**: install from clone to working task with the launcher only. Record exact steps in SHIP.md.

**Exit gate:** a non-technical user can go from download to approved change without opening a terminal (launcher does it).

### Phase 2 — Usability + hardening sign-off
1. **D-14 usability pass with a real non-developer** (your friend): task "make the label red" and one code-writing task. Watch them judge the approval cards; fix what confuses them.
2. **Coverage gate**: `pytest --cov` ≥80% on operator/src, 100% on model.py/schema.py/fsguard.py.
3. **osv-scanner clean** (or accepted risks with reasons+expiry), secrets clean (already true), SBOM committed for the release.
4. **gitleaks soft-fail → hard fail** (P3-11), and the secrets gate can no longer be bypassed by deleting a digest file.
5. **WCAG 2.2 AA quick pass**: keyboard-only run of the whole UI, focus visibility, contrast, semantic labels (already built in; verify).

**Exit gate:** friend completes a change unaided; all quality gates green; SHIP.md lists no unexamined defaults.

### Phase 3 — Production statement and release
1. **Tag `v1.0.0`** with release notes: what it does, who it's for, known limits (T2/T3 only, no T1 headset capture, no export-template debugger cells, CPU inference latency).
2. **Artifacts**: source zip, SBOM, checksums, and the floorplan map (optional but useful for onboarding).
3. **Policies**: LICENSE split (MIT addon/layer, AGPL operator), NOTICE, SECURITY.md (loopback model, token handling, egress trade-off, reporting), CHANGELOG from W0→v1.
4. **Public statement**: "Build XR experiences by describing them. Local-first, vendor-clean, human-approved." Include the privacy boundary in one sentence (D-19: dev-side, not hardware-side).

**v1 is done when:** a real non-developer installs it on a clean machine, makes a change with an approval they understand, and the audit log proves what happened — with every CI gate green and no untested claim presented as tested.

---

## 4. Build strategy (how to keep it honest)

- **Evidence-executed, always.** No card closes without a command and its output. This already caught: unformatted files, a docstring tripping the bind gate, a health-check that ignored digest pins, and a Referrer-Policy that nullified its own fallback.
- **No gate relaxations.** If something can't pass a gate, fix the code or record the exception with reason+expiry — never weaken the gate.
- **Small commits, one concern each**, formatted with the locked ruff before pushing, verified again on exact remote bytes (this bit us twice).
- **One orchestrator, exclusive file ownership, explicit-path staging** (`git add -A` is banned during parallel work).
- **Local-first, not local-only.** Hosted models are opt-in with the §3.6 disclosure; D-15 (Kimi) and future hosted adapters inherit every gate.
- **Roadmap discipline:** Godot (v1) → Blender (D-16) → Unity/Unreal (D-19). Each new engine must fit the Driver contract with identical gates; if it can't, it doesn't ship.
- **Device story stays free:** output is ordinary engine projects; OpenXR runtimes handle hardware. No Meta services required, ever.

---

## 5. The floorplan (interactive map)

Generated with [haydenschmitty/floorplan](https://github.com/haydenschmitty/floorplan) (MIT) using its real scan+build pipeline on this repo. Open `docs/floorplan/index.html` in any browser (offline, self-contained). Start with the **Start here** tour: Demo app → Addon → Action loop → Control panel → CI gates. Double-click any part to see its files and what it talks to; routes on the UI show the token-gated endpoints. It's the fastest way to explain the system to a new contributor or to your future self.

---

## 6. Immediate next actions (unchanged, now in one place)

1. **Orchestrator:** apply the ci.yml 2c + gdUnit4 edit (prompt in the previous message).
2. **QA:** run the contract roundtrip and file the done-card.
3. **You:** re-run the pinned UI task once (digest-enforced form), then hand the launcher to your friend for the D-14 test.
4. **Release when Phase 0–3 are green:** tag, artifacts, SECURITY.md, release notes.
