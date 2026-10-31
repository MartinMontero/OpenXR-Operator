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
| qwen2.5vl:7b (Ollama model, runtime not Python) | digest-pinned 2026-10-30 (S-09) | Apache-2.0 (Qwen weights licence varies by model — verify at register time) | n/a (runtime model, not a vendored dependency) | n/a | `qwen2.5vl:7b@sha256:5ced39dfa4bac325dc183dd1e4febaa1c46b3ea28bce48896c8e69c1e79611cc` (pulled + digest read from `/api/tags`, `runs/w4-ui/api-tags.json`) |
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
abnormal exit 103) and requires `--ignoreHeadlessMode`. Two more executed findings
(2026-10-30): v6.2.2's CI runner is **fail-fast by default**
(`_executor.fail_fast(true)` in GdUnitTestCIRunner `_ready`; reproduced with
a 4-test probe suite: a failing test aborts the rest of the suite), so add
`-c` ("run the complete test set") or a red step hides later results; and
the addon self-tests land in `addons/openxr_operator/tests/`
(W2-01-addon-server), a second `-a`.

Requested CI step (all flags executed locally):

```yaml
      - name: gdUnit4
        run: |
          godot --headless --path demo_project \
            -s addons/gdUnit4/bin/GdUnitCmdTool.gd \
            -a addon/tests -a addons/openxr_operator/tests \
            -c -rd reports --ignoreHeadlessMode
```

CONFIRMED by execution: `-rd` is interpreted **relative to the project path**
(`demo_project/`), not the cwd — `-rd reports` lands in `demo_project/reports/`.
Everything else in the kit snippet (test path `addon/tests`, `-rd`)
was executed locally and works unchanged. Note the gdUnit4 process exit code
surfaces inside its own log ("Exit code: 0"); the wrapper Godot process
returned rc=0 in both the pass and the refuse cases, so CI should also grep
the report/log — recommend `findstr`/grep for `Overall Summary:.*0 failures`
or parse `reports/report_*/results.xml`, rather than trusting `$?` alone.

## 2b. CI render suite (W2-02-addon-capture) — display + audio requirements

`addon/openxr_operator/tests_render/` exercises real viewport readback
(TC-SEC-005). Executed findings from bringing it up on Windows (2026-10-30):

- It CANNOT run headless: the dummy RenderingServer produces no frames.
  CI needs `xvfb-run -a` for this suite (same pattern as the kit's
  flow-smoke job).
- It needs `--audio-driver Dummy` on hosts without an audio device: without
  it, WASAPI init errors stall the main loop and tests time out (executed).
- gdUnit4's GdUnitCmdTool minimizes its window at startup; the suite
  restores it in before() and fails LOUDLY with a named environment error
  if the host cannot present a frame (no silent skips).

Requested CI addition (flags executed locally, xvfb itself UNTESTED here —
Windows host):

```yaml
      - name: gdUnit4 render suite (capture)
        run: |
          xvfb-run -a godot --path demo_project --audio-driver Dummy             -s addons/gdUnit4/bin/GdUnitCmdTool.gd             -a addons/openxr_operator/tests_render -c -rd reports-render
```

## 2c. ci.yml parse step needs project context (root-caused on Linux Godot 4.7.1, 2026-10-30)

The static job's GDScript parse step runs `--check-only` from the repo root with
no project context, so `res://addons/...` preloads don't resolve. Root-caused on
real Linux Godot 4.7.1 by the orchestrator session; the fix below was verified
there and re-verified on this Windows host (full addon sweep: every `.gd` under
`addon/openxr_operator/` parses clean via `--path demo_project --check-only`,
after `--import`; log `runs/w2-ci-parse/`). Requested replacement:

```yaml
      - name: Import demo project (class cache for parse)
        run: timeout 120 godot --headless --path demo_project --import
      - name: GDScript parse check
        run: |
          find addon -name '*.gd' -print0 | while IFS= read -r -d '' f; do
            timeout 60 godot --headless --path demo_project --check-only --script "$(realpath "$f")" \
              || { echo "::error file=$f::parse failed"; exit 1; }
          done
```

The addon-side companion fixes (Variant-inference lines that `--check-only`
escalates to errors) landed in the addon commit referenced below — server.gd
constant-time compare and two test declarations are now explicitly typed.

## 2d. S-09 model digest pinning — adapter gap (executed 2026-10-30, ollama 0.40.7)

Ollama 0.40.7 rejects `model@sha256:<digest>` on `/api/chat` AND `/api/show`
(400 "invalid model name"; executed probe `runs/w4-ui/ollama_digest_probe.py`).
The bare digest ID (`5ced39dfa4ba`) IS accepted by `/api/chat`
(content-addressed — the strongest pin form), but the adapter's `health()`
then fails because it checks for tag `<id>:latest`. So today there is no
adapter-supported way to run pinned: tag works but isn't pinned; digest-id is
pinned but fails health.

Request (operator zone): make `health()` digest-aware — when the configured
model carries a pin (`@sha256:…` or bare 12-hex), compare `/api/tags`
digest(s) for the matching tag/ID against the pin and fail closed on
mismatch; send the tag (or the working digest-ID form) on `/api/chat`. Until
then the digest is verified out-of-band (see VERIFICATION.md loop 2026-10-30
evening, check 5) — honest but manual.

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
