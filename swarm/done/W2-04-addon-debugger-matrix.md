# W2-04-addon-debugger-matrix — EngineDebugger channel availability (S-07)

| Field | Value |
|---|---|
| Wave | W2 |
| Owner | oxr-w-addon |
| Writes | `addon/openxr_operator/editor_bridge.gd`, docs section in the module docstring |
| Depends on | W2-01-addon-server |
| Findings | F-011, S-07 |

## Scope (RPI)

Editor-side work goes over the EngineDebugger capture channel
(`openxr_operator:*`, per `protocol.gd`), never `EditorInterface` from the
game process (F-011).

- Implement the debugger-channel endpoint used by `editor_rescan`.
- S-07 deliverable: a measured matrix — channel availability across build
  types (editor run, debug export, release export), each cell CONFIRMED by
  execution or marked UNTESTED with the reason. No cell is claimed from
  documentation alone.
- Where the channel is unavailable (e.g. release export), `editor_rescan`
  fails loudly with a named error, never silently no-ops.

## Mandatory tests (executed evidence required)

- Editor run: message round-trip over `openxr_operator:*` executed, output
  pasted.
- Release export: unavailability path exercised, named error observed.
- Matrix committed in the module docstring (or `addon/openxr_operator/DEBUGGER.md`
  if it outgrows a docstring), every cell labelled per the epistemic rules.

## Done when

Matrix complete with executed cells, evidence pasted, commit(s) reference
`W2-04-addon-debugger-matrix`, S-07 and F-011, card moved to `swarm/done/`.

## Executed evidence (oxr-w-qa on the addon plane per human direction 2026-10-30) — DONE

Delivered: addon/openxr_operator/editor_bridge.gd (game-side endpoint),
addon/openxr_operator/DEBUGGER.md (S-07 measured matrix),
addon/openxr_operator/tests/editor_bridge_test.gd (3 tests),
demo_project/oxr_harness.gd (runtime wiring: server+capture+inject+bridge,
active under debugger or --oxr-harness), demo_project/addons/oxr_debug_probe/
(demo-local editor-side capture fixture).

**Mandatory tests — executed:**
- **Editor run round trip over openxr_operator:* (CONFIRMED, 2026-10-30):**
  windowed editor (`-e --oxr-autoplay`, demo probe plugin) launched main.tscn
  with debugger attached; session active=true; external Python client drove the
  harness server: auth ok → editor_rescan → editor captured
  `openxr_operator:rescan`, executed `EditorInterface.get_resource_filesystem().scan()`
  (scanned=true), acked; bridge received the ack and replied
  `{ok: true, ack: ["rescan", true, 15392]}`. All 6 client checks PASS.
  Logs: runs/w2-04-addon-debugger/24-editor.log, 25-client.log;
  game-side user://oxr_game_debug.log.
- **Unavailability path (CONFIRMED):** plain/headless process (== release-export
  code path): channel_available() false; editor_rescan →
  `{ok:false, error:"editor_rescan unavailable: EngineDebugger is inactive …"}`
  on the wire AND push_warning (asserted via assert_error().is_push_warning);
  connection stays up. gdUnit4 suite: 32/32 green, exit 0, two consecutive runs
  (runs/w2-04-addon-debugger/27-suite-run2.log, 28-suite-final.log).
- **Matrix committed** in addon/openxr_operator/DEBUGGER.md — every cell
  CONFIRMED-by-execution or UNTESTED-with-reason. Export-binary cells UNTESTED:
  no export templates on host (%APPDATA%\Godot\export_templates empty).

**Executed findings (in DEBUGGER.md):** editor debugger listens on 6006 here
(not 6007); editor-side _capture gets the full prefixed message while the
game-side capture gets it prefix-stripped ("ack") — bridge accepts both;
--remote-debug into a listening editor connects but the session is NOT active
(captures don't fire) — editor-launched is the working shape; headless editor
loads plugins but opens no debugger port; first editor fs scan can exceed 10 s.

pytest 71 passed / 1 skipped; gdlint/gdformat clean.

Commit references W2-04-addon-debugger-matrix, S-07, F-011.
