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
