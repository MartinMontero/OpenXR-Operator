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
