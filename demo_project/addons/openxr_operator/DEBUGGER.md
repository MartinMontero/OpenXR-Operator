# S-07 — EngineDebugger channel availability matrix (W2-04-addon-debugger-matrix)

Channel: `openxr_operator:*` (protocol.gd `DEBUGGER_CAPTURE`), over
EngineDebugger message captures. Game-side endpoint: `editor_bridge.gd`.
Editor-side fixture used for measurement: `demo_project/addons/oxr_debug_probe/`
(demo-local; the addon's production `plugin.gd`/`debugger_plugin.gd` is an
escalated scheduling gap).

Every cell is CONFIRMED by execution (evidence named) or UNTESTED with the
reason. Nothing here is claimed from documentation alone.

| Build / run type | Channel available? | Evidence |
|---|---|---|
| Editor run (game launched by the editor, debugger attached) | **CONFIRMED — full round trip** | 2026-10-30: windowed editor (`-e --oxr-autoplay`, probe plugin) played `main.tscn`; game's harness server took `editor_rescan` over the wire; editor captured `openxr_operator:rescan`, ran `EditorInterface.get_resource_filesystem().scan()` (scanned=true), acked; game bridge received ack and replied `{ok: true, ack: ["rescan", true, ...]}`. Logs: `runs/w2-04-addon-debugger/24-editor.log`, `25-client.log`, game-side `user://oxr_game_debug.log` |
| Game with `--remote-debug` to a listening editor (not editor-launched) | **CONFIRMED — channel connects (`is_active()` true) but the session is NOT active** (`EditorDebuggerSession.is_active()` false); editor captures do not fire. Editor-launched is the working shape. | `runs/w2-04-addon-debugger/07-editor-instrumented.log` (`sessions=1 states=[[false, false]]`), `08-game-instrumented.log` |
| Headless editor (`-e --headless`) as debugger host | **CONFIRMED — editor plugins load and register the capture; nothing listens on the debugger port** (connection refused from the game) | `runs/w2-04-addon-debugger/01-editor-import.log` (plugin loaded), `03-game-roundtrip.log` ("Remote Debugger: Unable to connect") |
| Plain process, no debugger (headless or not) == the release-export code path | **CONFIRMED — unavailable, fails loudly** | gdUnit4 `tests/editor_bridge_test.gd`: `channel_available()` false, `editor_rescan` → `{ok:false, error:"…EngineDebugger is inactive…"}`, connection stays up, push_warning asserted |
| Debug export binary | **UNTESTED** — no export templates on host (`%APPDATA%\Godot\export_templates` is empty, 2026-10-30). Expectation (INFERRED, not claimed): behaves like editor run only when launched with `--remote-debug` into a listening editor; otherwise the inactive path | — |
| Release export binary | **UNTESTED** — same missing-templates reason. The unavailability code path (EngineDebugger inactive → named error) is the identical branch exercised in the plain-process cell | — |

## Executed protocol findings (recorded for the addon's future plugin.gd)

- Editor debugger listens on **6006**, not the oft-assumed 6007, on this
  4.7.1 install (netstat evidence in session logs).
- **Asymmetry:** editor-side `EditorDebuggerPlugin._capture` receives the full
  message (`openxr_operator:rescan`); the game-side capture callable receives
  the message with the capture prefix **stripped** (`ack`). `editor_bridge.gd`
  accepts both forms.
- The first editor filesystem scan after play can take >10 s; the bridge ack
  budget in the demo harness is 30 s (`ack_timeout_ms`, code-only knob).
- Editor-run games have stdout captured by the editor UI; the bridge logs to
  `user://oxr_game_debug.log` for evidence.
