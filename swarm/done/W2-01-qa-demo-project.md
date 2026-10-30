# W2-01-qa-demo-project — Demo project skeleton + gdUnit4 harness

| Field | Value |
|---|---|
| Wave | W2 |
| Owner | oxr-w-qa |
| Writes | `demo_project/` (assigned to QA by human direction 2026-10-29 — supersedes the P-1 role-text line giving `demo_project/` to oxr-w-addon; reconcile the prompt text at next prompt edit), plus `flows/`, `runs/` as needed |
| Depends on | — (first W2 card chronologically; unblocks all addon/operator integration tests) |
| Findings | W0-06, S-05 (mapping part), S-12 (register entry), W0-07 (gdUnit4 version per kit) |

## Scope (RPI)

Land the minimal executable Godot project the whole wave tests against:

- `demo_project/` — Godot 4.7.1 project, `res://scenes/main.tscn` (the path
  `flows/smoke.yaml` already references), the addon installed and enabled.
- Scene content sufficient for the contract commands: a labelled control with
  known text (`assert_visible`, `get_property`), a small node tree with
  stable names (`scene_tree`), a settable property (`set_property`), and a
  black-render scene variant for TC-SEC-005 fixtures.
- **S-05 (mapping part):** the demo install follows — and thereby proves —
  the addon install mapping. Write the steps you actually executed into
  `demo_project/INSTALL.md`. The full end-user runbook is W5 scope.
- **gdUnit4 ≥ 6.2.0** (S-12): vendored per the kit's licence rules, with the
  executed headless dry-run that W0-06 scheduled here — `godot --headless`
  gdUnit4 invocation plus a `--import` pass, output pasted. Label per W0-06
  until executed: it is currently NOT ATTEMPTED.
- **Escalation:** `docs/dependency-register.md` does not exist on main at
  card time (W1 was closed without it landing locally). The gdUnit4 register
  entry (S-12) and the CI gdUnit4 step touch orchestrator-owned files —
  request them via `swarm/requests/`; do not edit `docs/` or
  `.github/workflows/` directly.

## Mandatory tests (executed evidence required)

- Headless import + scene load of `main.tscn`, rc=0, output pasted.
- gdUnit4 headless dry-run executed (closes W0-06).
- `flows/smoke.yaml` parses against the demo project path (model-disabled,
  T3) as far as the W2 planes allow; any step that cannot run yet is named,
  not skipped silently.

## Done when

Demo project loads headless in CI-equivalent local execution, W0-06 evidence
pasted, register/CI escalations filed, commit(s) reference
`W2-01-qa-demo-project` and finding ids, card moved to `swarm/done/`.

## Executed evidence (oxr-w-qa, 2026-10-29) — DONE

Environment: Windows 11, Godot 4.7.1.stable.official.a13da4feb, gdUnit4
v6.2.2 @ 0127a55f4543dfc24746f6e5c7ba6f94105d51f2 (MIT, zip SHA-256
58a391b0c85cbbcf7aeb09b718c8173793d45ab511950cd65eec0183aabf0e50).

- Landed: demo_project/ (project.godot, scenes/main.tscn, scenes/black.tscn,
  addon/tests/demo_harness_test.gd, INSTALL.md, VENDORED.md);
  addons/openxr_operator installed per mapping; addons/gdUnit4 vendored.
  Scenes provide: StatusLabel text "STATUS: IDLE" (assert_visible,
  get_property), stable names World/XROrigin/Controller{Left,Right}
  (scene_tree), settable Label.text (set_property), black ColorRect fixture
  (TC-SEC-005).
- Headless import: `godot --headless --path demo_project --import` rc=0
  (runs/w2-01/01-import.log). Two non-fatal ERROR lines: plugin.gd absent
  (CONFIRMED gap — addon skeleton has no plugin.gd; escalated).
- Scene loads: main.tscn rc=0 (02-scene-load.log), black.tscn rc=0
  (03-black-scene-load.log).
- W0-06 gdUnit4 dry-run EXECUTED: 4/4 test cases PASSED, 0 errors/failures/
  orphans, gdUnit4 exit code 0 (04-gdunit4-dry-run.log,
  gdunit4-reports/report_1/). CONFIRMED: v6.2.2 refuses plain --headless
  (exit 103); --ignoreHeadlessMode required — CI snippet fix escalated.
- flows/smoke.yaml parse (model-disabled, T3): PASS rc=0, header/tiers/
  vocabulary valid, project+scene resolve (05-smoke-parse.log). Steps not
  runnable yet (named, not skipped): launch/settle/capture await
  W2-01-addon-server and W2-02-operator-driver.
- Operator regression: pytest 52/52 passed (06-pytest.log).
- Full ledger: VERIFICATION.md (loop 2026-10-29).
- Escalations filed: swarm/requests/W2-01-qa-register-ci-requests.md
  (S-12 register row + NOTICE line, CI gdUnit4 step with --ignoreHeadlessMode,
  plugin.gd scheduling gap, W0-06 relabel EXECUTED).

Findings referenced: W0-06 (closed by execution), W0-07 (gdUnit4 version per
kit satisfied: v6.2.2 >= 6.2.0), S-05 (mapping part proven; runbook is W5),
S-12 (register entry escalated — register file does not exist on main).
