# Request: dependency-register entry + CI gdUnit4 step + plugin.gd scheduling gap

**From:** oxr-w-qa
**Date:** 2026-10-29
**Card:** W2-01-qa-demo-project (escalation clause: `docs/` and `.github/workflows/` are orchestrator-owned)
**Findings:** S-12, W0-06 (closed by execution, evidence below), W0-07

Three orchestrator-owned items surfaced by executing W2-01. QA does not edit
`docs/` or `.github/workflows/` directly; requesting here.

## 1. Create `docs/dependency-register.md` and add the gdUnit4 row (S-12)

`docs/dependency-register.md` does not exist on main (W1 closed without it
landing — confirmed by `dir docs\` on 2026-10-29). PLAN.md §5.3 assigns it to
the orchestrator. Once it exists, the executed row for gdUnit4 is:

| Dependency | Version | Licence | AGPL-compatible | Vendor gate | Pin |
|---|---|---|---|---|---|
| gdUnit4 | v6.2.2 (≥ 6.2.0 per S-12/W0-07) | MIT | Yes | Pass | commit `0127a55f4543dfc24746f6e5c7ba6f94105d51f2`, zip SHA-256 `58a391b0c85cbbcf7aeb09b718c8173793d45ab511950cd65eec0183aabf0e50` |

Upstream moved: `MikeSchulze/gdUnit4` now redirects to
`godot-gdunit-labs/gdUnit4` (CONFIRMED by execution of the GitHub API,
2026-10-29). Full provenance in `demo_project/VENDORED.md`.

Also NOTICE (root, orchestrator-owned): the vendored gdUnit4 tree is a new
third-party attribution. Its MIT `LICENSE` ships in place at
`demo_project/addons/gdUnit4/LICENSE`, but per kit §4.1 "Keep `LICENSES/` and
`NOTICE` accurate", NOTICE needs a gdUnit4 line. QA has not edited NOTICE.

## 2. CI gdUnit4 step (kit §7.2 snippet needs one fix)

The kit's step predates a gdUnit4 behaviour change that QA hit by execution:
v6.2.2 **refuses plain `--headless`** ("Headless mode is not supported!",
abnormal exit 103) and requires `--ignoreHeadlessMode`. Requested CI step:

```yaml
      - name: gdUnit4
        run: |
          godot --headless --path demo_project \
            -s addons/gdUnit4/bin/GdUnitCmdTool.gd \
            -a addon/tests -rd reports --ignoreHeadlessMode
```

CONFIRMED by execution: `-rd` is interpreted **relative to the project path**
(`demo_project/`), not the cwd — `-rd reports` lands in `demo_project/reports/`.
Everything else in the kit snippet (test path `addon/tests`, `-rd`)
was executed locally and works unchanged. Note the gdUnit4 process exit code
surfaces inside its own log ("Exit code: 0"); the wrapper Godot process
returned rc=0 in both the pass and the refuse cases, so CI should also grep
the report/log — recommend `findstr`/grep for `Overall Summary:.*0 failures`
or parse `reports/report_*/results.xml`, rather than trusting `$?` alone.

## 3. Scheduling gap: `addon/openxr_operator/plugin.gd` has no owner

`plugin.cfg` declares `script="plugin.gd"`; `plugin.gd` does not exist on main
and no W2 addon card (W2-01 server, W2-02 capture, W2-03 inject, W2-04
debugger matrix) schedules it — `findstr plugin.gd swarm\tasks\W2-0*.md`
returns nothing. Consequence (executed): enabling the addon per its own
`plugin.cfg` logs `Failed loading resource: res://addons/openxr_operator/plugin.gd`
on every import (non-fatal, rc=0). Request: schedule `plugin.gd` (kit §2.6
layout lists it as the EditorPlugin: autoload + debugger-plugin registration)
on the addon plane, or rule that the plugin is intentionally not enabled until
then.

## 4. Commit-hygiene flag (executed observation, not a request to rewrite)

Orchestrator commit `8cfc4e2` ("W2-01-orchestrator-adapters done …") swept
QA's untracked, in-progress `demo_project/` tree into its `git add` (verified
via `git show 8cfc4e2 --stat`: 35+ `demo_project/` paths under an
orchestrator-adapters message). The content is bit-identical to what QA
verified, so no rework is requested — but the wave's "commits reference the
card and finding ids" rule is weakened when cross-role files ride along.
Request: workers stage by path, not `git add -A`, while sessions run
concurrently in one working tree.

## W0-06 closure evidence (executed 2026-10-29)

- `godot --headless --path demo_project --import` → rc=0 (`runs/w2-01/01-import.log`)
- `godot --headless --path demo_project -s addons/gdUnit4/bin/GdUnitCmdTool.gd -a addon/tests -rd runs/w2-01/gdunit4-reports --ignoreHeadlessMode`
  → 4/4 test cases PASSED, 0 errors, 0 failures, 0 orphans, gdUnit4 exit code 0
  (`runs/w2-01/04-gdunit4-dry-run.log`, `runs/w2-01/gdunit4-reports/report_1/`)

W0-06 was labelled NOT ATTEMPTED in AUDIT.md; it is now EXECUTED. Request the
orchestrator update AUDIT.md W0-06 accordingly (docs/ is orchestrator-owned).
