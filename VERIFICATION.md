# VERIFICATION.md

Executed evidence only. States: CONFIRMED / INFERRED / BLOCKED / NOT ATTEMPTED / UNTESTED.
Run artifacts live under `runs/` (git-ignored); this file records what ran and where the log is.

## Loop 2026-10-29 — W2-01-qa-demo-project harness bring-up

Scope note: this is the harness bring-up loop, not a full verification loop.
The full loop (clean build, all gates, all flows model-disabled then
model-enabled) is not runnable yet: the addon server (W2-01-addon-server) and
the operator flow runner (W2-02-operator-driver) have not landed. No
model-enabled anything exists to run; nothing here claims otherwise.

Environment: Windows 11, cmd, Godot 4.7.1.stable.official.a13da4feb
(`C:\Users\User\dev\tools\godot\Godot_v4.7.1-stable_win64.exe`),
gdUnit4 v6.2.2 @ 0127a55f.

| # | Check | Command | Result | Evidence |
|---|---|---|---|---|
| 1 | Headless import pass (W0-06) | `godot --headless --path demo_project --import` | PASS, rc=0. Two ERROR lines: `plugin.gd` not found (CONFIRMED gap, escalated — addon skeleton has no plugin.gd; non-fatal) | `runs/w2-01/01-import.log` |
| 2 | Scene load `main.tscn` | `godot --headless --path demo_project res://scenes/main.tscn --quit-after 5` | PASS, rc=0, no errors | `runs/w2-01/02-scene-load.log` |
| 3 | Scene load `black.tscn` (TC-SEC-005 fixture) | `godot --headless --path demo_project res://scenes/black.tscn --quit-after 5` | PASS, rc=0, no errors | `runs/w2-01/03-black-scene-load.log` |
| 4 | gdUnit4 headless dry-run (closes W0-06) | `godot --headless --path demo_project -s addons/gdUnit4/bin/GdUnitCmdTool.gd -a addon/tests -rd <abs>/runs/w2-01/gdunit4-reports --ignoreHeadlessMode` | PASS: 4/4 test cases, 0 errors, 0 failures, 0 orphans, gdUnit4 exit code 0 — **run twice consecutively, green both times**. First attempt without `--ignoreHeadlessMode` refused with abnormal exit 103 (gdUnit4 v6.2.2 headless guard — CONFIRMED, escalated for CI). CONFIRMED: `-rd` is project-relative; absolute path used to keep reports under `runs/` | `runs/w2-01/04-gdunit4-dry-run.log`, `runs/w2-01/gdunit4-reports/report_1/` |
| 5 | `flows/smoke.yaml` structural parse, model-disabled (T3) | `uv run --project operator python runs/w2-01/check_smoke_parse.py` | PASS, rc=0: YAML parses; header keys/tiers valid per `docs/contracts/flow-schema.md`; capabilities `[]` (deny-all) intact; `project: ./demo_project` and `scene: res://scenes/main.tscn` resolve on disk; all 3 steps in command vocabulary | `runs/w2-01/05-smoke-parse.log` |

### flows/smoke.yaml step ledger (per flow-schema contract)

| Step | Command | Capture tier | Inject tier | Settle outcome |
|---|---|---|---|---|
| 0 | `launch {clean: true}` | — | — | NOT RUNNABLE YET — needs addon server + operator driver (W2 planes not landed) |
| 1 | `settle {timeout: 8000}` | — | — | NOT RUNNABLE YET — same. `on_timeout` absent, so the S-15 parse-time validation has nothing to reject |
| 2 | `capture {label: "after-launch"}` | t3 (header) | a3 (header) | NOT RUNNABLE YET — capture plane is W2-02-addon-capture |

Un-runnable steps are named, not skipped silently, per the card.

### Security spot-checks this loop (executed, not read)

- Vendor gate on the new Python side: `uv run --project operator pytest -q` —
  see below; vendor scan itself runs inside that suite (TC-SEC-010).
- gdUnit4 zip hash pinned and recorded (`demo_project/VENDORED.md`); vendored
  tree copied unmodified from the pinned commit.
- Token surface: none yet — no server code exists to generate
  `user://openxr_operator.token`. UNTESTED (addon plane).

### Operator suite regression (addon bring-up must not break W1 gates)

Executed `uv run --project operator pytest -q` after landing the harness:
52/52 passed (log: `runs/w2-01/06-pytest.log`). CONFIRMED.

### Two-consecutive-clean-runs rule

Harness bring-up checks 1–3 and 5 ran once each; check 4 (gdUnit4) ran green
twice consecutively (second run after correcting the report path to absolute).
The wave-level "two consecutive clean full runs" rule applies to full
verification loops, which cannot exist until the server/driver planes land.
First full loop will re-run everything above.

### Coordination note (CONFIRMED, escalated)

Orchestrator commit `8cfc4e2` swept this session's untracked `demo_project/`
tree into a `git add -A`-style commit mid-verification
(`git show 8cfc4e2 --stat`). Content is bit-identical to the verified state;
no rework needed. Flagged in
`swarm/requests/W2-01-qa-register-ci-requests.md` item 4.

## Loop 2026-10-30 (evening) — W4 UI smoke with digest-pinned model (S-09)

| # | Check | Command | Result | Evidence |
|---|---|---|---|---|
| 1 | Model pull | `ollama pull qwen2.5vl:7b` | CONFIRMED: pulled 6.0 GB, present in `ollama list` (ID 5ced39dfa4ba) | `runs/ollama-pull.log` |
| 2 | S-09 digest pin | `GET /api/tags` | CONFIRMED: digest `5ced39dfa4bac325dc183dd1e4febaa1c46b3ea28bce48896c8e69c1e79611cc` (ID matches first 12 chars). Pin form: `qwen2.5vl:7b@sha256:5ced39dfa4bac325dc183dd1e4febaa1c46b3ea28bce48896c8e69c1e79611cc` | `runs/w4-ui/api-tags.json` |
| 3 | Demo engine + harness | `godot --path demo_project --audio-driver Dummy --oxr-harness` (windowed) | CONFIRMED: server bound 127.0.0.1:9099; Python client auth ok, scene_tree returned Main/StatusLabel/World, ping ok | `runs/w4-ui/engine_check.py` output (session log) |
| 4 | UI end-to-end (D-14 path) | `openxr-operator ui --project demo_project --token-file <engine token> --godot <godot exe>` | **CONFIRMED**: token gate 401/401/200, Origin gate 403, task accepted, approval card rendered plain-language (saved HTML: 'Change a property in your scene — Node: /root/Main/StatusLabel — Set text to: STATUS: RED', rationale labelled 'its words, not verified', no raw JSON — one probe heuristic false-fired on CSS class names, resolved by inspection), human approve → engine executed set_property → independent wire readback returned `STATUS: RED`; hash-chained audit records approval (approver=human) + execution + step-2 validation rejections; step-2 model output failed schema twice → aborted (kit §2.8 path working as designed) | `runs/w4-ui/ui3.log`, `drive_ui.py` output, `approval-card.html`, `audit-tail.jsonl` |
| 5 | S-09 digest addressing (executed) | ollama 0.40.7 `/api/chat` probes | CONFIRMED: `model@sha256:<digest>` → 400 invalid model name (chat AND /api/show); `model@<id12>` → 400; **bare digest ID `5ced39dfa4ba` → 200 works** (content-addressed), but adapter `health()` then fails (checks `id:latest` tag) — pin enforcement needs adapter support, escalated. Tonight's run used the tag with the digest verified against `/api/tags` immediately before the run | `runs/w4-ui/ollama_digest_probe.py`, `verify_pin.py` (pin match: True) |
| 6 | Token hygiene | — | temp copy `runs/w4-ui/engine.token` deleted after the run; engine token never logged | — |

S-09 register note: `docs/dependency-register.md` is orchestrator-owned and still
absent; the model digest row is escalated via
`swarm/requests/W2-01-qa-register-ci-requests.md`.
