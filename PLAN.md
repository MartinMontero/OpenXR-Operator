---
sources: docs/BUILD_KIT_v3.pdf (v3.2); AUDIT.md (W0 preflight); swarm/decisions/D-02…D-14
verified: 2026-08-11 (UTC)
---

# PLAN.md — OpenXR Operator

RPI plan. Ordered work mapped to kit waves W0–W6, suspects S-01…S-16,
findings F-001…F-030 (see §4 limitation), and the v3.2 amendments. Acceptance
is executable per item. Non-goals verbatim in §7.

## 1. Status legend

DONE = executed and evidenced in AUDIT.md §2. PART = partially present in
repo, exit gate not yet demonstrated. OPEN = not started. GATED = human stop
or dependency.

## 2. Wave map

| Wave | Scope (kit Table 6-1) | Exit gate | Status |
|---|---|---|---|
| W0 | Preflight & ingest (orchestrator) | Preflight report on disk; missing tools as P0; D-04/D-05 answered | **DONE** 2026-08-11 (AUDIT.md §2; D-04/D-05 in swarm/decisions/) |
| W1 | Repo, contracts, gates (orchestrator only); M0 + S-01, S-09, S-10, S-12, S-13 | CI green on empty codebase; vendor gate demonstrably fails when `openai` is added to the lockfile and passes when removed; tag-pinned Action demonstrably fails the digest gate | **DONE** — closed by the human 2026-10-29, CI green |
| W2 | Planes behind contracts; M1–M3 + S-02…S-07, S-16 | Unauth command closes connection; wrong version clear; 1 MiB frame rejected; 51st msg/s closes peer; non-black capture at declared tier; bogus tracker raises; traversal rejected+logged | OPEN — cards written 2026-10-29 (`swarm/tasks/W2-*`: 4 addon, 2 operator, 1 orchestrator, 2 QA) |
| W3 | Flow runner; M4 | Demo flow headless in CI, model disabled, complete run bundle; no sleep; timeout ±50ms executed | OPEN |
| W4 | Agent loop; M5 + S-08, S-09, S-11, S-14 | Mutating action cannot execute without approval record (attempted, logged); schema-violating output rejected/retried-once/aborted; sandbox unavailable ⇒ mutating flows refuse loudly; envelope measured in README | OPEN |
| W5 | Web UI & install; M6 + S-05, S-14 | No third-party origin in any response; page works unplugged; WCAG baseline; install runbook executed from scratch | OPEN |
| W6 | Layer (T1/A2); M7 | Layer frame differs measurably from T2 under stereo; no implicit manifest; per-process activation only | **GATED — D-04 answered DEFER (2026-08-11). Do not start.** |

## 3. Suspect → wave mapping (kit Part 4)

| ID | Fix (wave) | Status |
|---|---|---|
| S-01 digest-pinned Actions | W1 | DONE — both directions executed 2026-10-28 (tag-pinned scratch workflow fails RC=1; real workflows pass); failure-path diagnostic bug found by execution and fixed (BASH_REMATCH clobbered under `set -u`) |
| S-02 token-file permissions honesty | W2 (addon) | OPEN |
| S-03 class-name fix + `inject.gd` deliverable | W2 (addon) | OPEN |
| S-04 dead symlink check removal; TOCTOU doc | W2 (operator) | OPEN |
| S-05 install mapping/runbook | W2/W5 | OPEN |
| S-06 num_ctx 8192 measurement | W2 (operator) | OPEN |
| S-07 debugger-channel matrix | W2 (addon) | OPEN |
| S-08 hash-chained audit log + verifier | W4 | OPEN |
| S-09 model digest pinning | W1 scaffold / W4 pin+SBOM | PART — §5.3 |
| S-10 checksum-verify CI binaries | W1 | PART — gitleaks verified (CONFIRMED); Godot zip unverified (W0-04, §5.2) |
| S-11 hardware envelope | W0 measured / W4 final floor | PART — W0 inventory CONFIRMED; latency UNTESTED |
| S-12 gdUnit4 ≥ 6.2.0 in register + CI | W1 | OPEN — no register exists (§5.3) |
| S-13 re-date Qwen3-VL note | W1 | OPEN — fold into register (§5.3) |
| S-14 approval batching + latency record | W4/W5 | OPEN |
| S-15 on_timeout parse-time validation | W3 | OPEN |
| S-16 auth nits documented | W2 | OPEN |

## 4. Kit F-001…F-030 mapping

Limitation (AUDIT.md W0-07, BLOCKED): the F-ledger's full text is in build kit
v2.0, absent from this repo. Mapping below covers the F-IDs v3.2 references
explicitly; the remainder are dispositioned at design level by kit v2.0 and
re-verified per owning wave; SHIP.md carries the full table, each marked
re-confirmed-by-execution or UNTESTED.

| F-ID | v3.2 reference | Owning wave | Status |
|---|---|---|---|
| F-002 | 0.0.0.0 bind (ci.yml bind gate) | W1 gate / every loop | Gate green (CONFIRMED, dry-run) |
| F-010 | exact composited-frame capture | W6 | DEFERRED with D-04; disclose in README + SHIP.md |
| F-011 | EditorInterface editor-only | W2 editor bridge via EngineDebugger | OPEN |
| F-028 | docs-vs-code typo (never-run evidence) | all | Standing: executable claims executed |
| F-030 | WCAG 2.2 AA baseline | W5 | OPEN |

## 5. W1 remaining work (orchestrator executes)

1. **osv-scanner gate (W0-03).** Add an osv-scanner step to ci.yml (Action
   pinned by commit digest, or binary checksum-verified per the gitleaks
   pattern); dry-run it locally; never Trivy.
2. **Godot zip checksum (W0-04).** Pin the Godot 4.7.1 `SHA512-SUMS.txt`
   digest in ci.yml and verify the downloaded zip against it; dry-run the
   verification locally.
3. **Dependency register (S-12, S-13, S-09 scaffold).** Create
   `docs/dependency-register.md`: every dependency with version pin and gate
   cross-ref — gdUnit4 ≥ 6.2.0 (S-12, R-7); re-dated Qwen3-VL caution
   (S-13: fixes recorded downstream 2026.4.x, "verify your exact tag"
   stands); model-digest pinning scaffold for `ollama pull
   model@sha256:…` (S-09) with the CI check wired at W4.
4. **W1 exit-gate demonstrations — DONE 2026-10-28** (evidence in AUDIT.md §6):
   - vendor gate fails when `openai` is added to a lockfile copy, passes
     pristine — TC-SEC-010 (`operator/tests/test_vendorscan_gate.py`),
     executed in pytest, both directions (P1-01);
   - digest gate fails on a tag-pinned `uses:` line — executed on a scratch
     workflow (`actions/checkout@v4` → RC=1, clean diagnostic); the demo
     exposed a failure-path bug (BASH_REMATCH clobbered by the second regex
     under `set -u`), fixed in `tools/check-action-pins.sh`.
5. **Freeze check.** Confirm the five contracts on disk match kit §2.2
   (protocol.gd, driver.py, schema.py, flow JSON Schema, model.py+backends/);
   record freeze commit in PLAN.md history.

## 6. Decisions (register; none assumed)

- ANSWERED: D-02, D-04 (2026-08-11, examined defaults), D-05 (2026-08-11,
  WSL2+bwrap, smoke-tested), D-10…D-14 (prior session).
- ANSWERED 2026-08-11 (landed 2026-10-28): D-15 (hosted_moonshot/Kimi
  adapter, opt-in future wave; D-12/D-13 unchanged), D-16 (Blender is a v2
  candidate; no v1 work).
- D-17 (orchestrator ruling, 2026-10-28): contract amendment P1-04 approved —
  observation content delimited as UNTRUSTED in `render_user_text()`.
- Defaults adopted, explicit: D-03 (MIT addon — implemented), D-09 (4.7.1
  pinned in CI).
- Unexamined defaults (resurface at ship time per stop points): D-01 (Linux
  first — W6, moot while D-04=defer), D-06 (never auto-apply — W4), D-07
  (build bridge — W2), D-08 (no OMBI — W3).

## 7. Non-goals for v1 (kit Part 8.4, verbatim)

Unity or Unreal. Cloud inference of any kind. Multi-agent orchestration of
the shipped agent (the swarm builds the product; it is not the product).
Voice input. Model fine-tuning. Godot Asset Store publishing. The OMBI Scene
Object Model (D-08). Any feature of v1.0's "Extending the Kit" section.

## 8. Verification & stop points

- Every wave ends with the kit §6.1 loop: clean build, all gates, all flows
  model-disabled then model-enabled, security spot-checks executed, results
  in VERIFICATION.md. Two consecutive clean full runs (three for flow/XR
  timing) before a wave is called done.
- Human stops: W6 start (D-04 — answered DEFER), any security-gate change,
  any Rule 9 action, any unlisted model, any D-decision on an unexamined
  default at ship time.

## History

- 2026-08-11 — W0 done; PLAN.md written; D-02/D-04/D-05 answered.
- 2026-10-28 — External audit (swarm/requests/external-audit-2026-08-11.md)
  remediated before W1 close: P1-01 (vendor gate scans uv.lock + tests;
  TC-SEC-010 both directions), P1-03 (gdformat/gdlint bypasses removed),
  P1-05 (Azure OpenAI + api.llama.com hosts denied), P2-06 (exact/leaf
  model-id tier), P1-04 via contract amendment D-17 (TC-SEC-009). Scheduled:
  P1-02 licence gate (W1/W2, SBOM-vs-metadata wiring decision pending),
  P2-07/P2-08/P2-09 adapter robustness (W2), P3-10 parse guards (W2),
  P3-11/P3-12 + coverage gate (SHIP checklist). W1 remainder before close:
  §5.1 osv-scanner (W0-03), §5.2 Godot zip checksum (W0-04), §5.3 dependency
  register, §5.5 freeze check.
- 2026-10-29 — W1 closed by the human (green). W2 cards written:
  W2-01..04-addon (server/auth+limits, capture T2/T3, inject A3+S-03,
  debugger matrix S-07), W2-01..02-operator (fsguard S-04+TC-SEC-003,
  driver/settle TC-SEC-004/007+S-06), W2-01-orchestrator-adapters
  (P2-07/08/09, P3-10 — backends/ and model.py are orchestrator-owned),
  W2-01..02-qa (demo project + gdUnit4 harness closing W0-06; contract
  round-trip replaying the W2 exit gate). Audit TC-SEC-001/002/005/006
  carried on the addon cards per human direction; demo project assigned
  to QA (supersedes the P-1 role text giving demo_project/ to the addon
  worker — reconcile at next prompt edit).
