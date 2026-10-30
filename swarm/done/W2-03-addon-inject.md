# W2-03-addon-inject — A3 injection floor, inject.gd deliverable (S-03)

| Field | Value |
|---|---|
| Wave | W2 |
| Owner | oxr-w-addon |
| Writes | `addon/openxr_operator/inject.gd`, class-name fixes across `addon/` |
| Depends on | W2-01-addon-server, W2-01-qa-demo-project |
| Findings | F-012, S-03; audit TC-SEC-006 |

## Scope (RPI)

Implement the `inject` command at the A3 floor (desktop harness input
synthesis; no OpenXR runtime involvement — D-04):

- Tracker names constrained to `left_hand` / `right_hand`; anything else is
  rejected before any injection attempt.
- Pose default applied when the request omits it.
- **Post-injection assertion** that an `XRController3D` bound. A silent no-op
  is a failure: binding to nothing raises, and the error is returned on the
  wire and logged.
- S-03 deliverable: `inject.gd` ships with class names that match what every
  other file references. Grep the tree for each `class_name` introduced and
  each reference to one; mismatches are build failures, not review comments.

## Mandatory tests (executed evidence required)

- **TC-SEC-006 (F-012):** injection binding to nothing raises, never no-ops.
  Fixture: inject with a valid tracker name in a scene with no compatible
  node → explicit error on the wire + log entry.
- Bogus tracker name (`"head"`, `"left-hand"`, empty) → rejected before
  injection, error names the constraint (W2 exit gate: bogus tracker raises).

## Done when

Tests executed green, evidence pasted, commit(s) reference
`W2-03-addon-inject`, S-03 and F-012, card moved to `swarm/done/`.

## Executed evidence (oxr-w-qa on the addon plane per human direction 2026-10-30) — DONE

Delivered: addon/openxr_operator/inject.gd + addon/openxr_operator/tests/inject_test.gd
(9 tests), installed per the S-05 mapping.

Executed 2026-10-30, Godot 4.7.1 headless, gdUnit4 v6.2.2
(`-a addon/tests -a addons/openxr_operator/tests -c --ignoreHeadlessMode
--audio-driver Dummy`), TWO consecutive clean runs
(runs/w2-03-addon-inject/02-final.log, 03-final-run2.log): **29/29 test cases,
0 errors, 0 failures, 0 orphans, exit code 0** (4 harness + 16 server + 9 inject).
pytest: 71 passed, 1 skipped. gdlint/gdformat clean.

Mandatory tests:
- **TC-SEC-006 (F-012):** inject move_controller with no XRController3D in the
  scene → wire reply `{ok: false, tier: "a3", error: "no XRController3D bound to
  tracker 'left_hand' (F-012: ...)"}`, connection stays up; the log line is
  asserted via gdUnit4 `assert_error().is_push_warning(...)` (exact message).
  PASSED both directions (wire + log).
- **Bogus trackers rejected pre-injection** (W2 exit gate): "head", "left-hand",
  "", "LEFT_HAND" via `tracker`, and hand "head" via `hand` — all rejected with
  an error naming the constraint ("must be one of left_hand/right_hand"), and the
  controller transform verified untouched (nothing injected). Rejection is also
  logged (is_push_warning). PASSED.

Also executed: pose lands on the bound node (position/rotation applied and
read back — the post-injection binding assertion); pose default when omitted;
press synthesizes Input action state (action_press/release reflected by
Input.is_action_pressed, auto-registers missing InputMap actions); press without
binding fails; unknown op is a named error.

**S-03 (class-name consistency):** proven by construction — no `class_name`
anywhere in addon/ (grep output pasted in session; only a comment mentions the
phrase). All cross-file references are preload paths, so there is no class-name
table to drift. gdlint enforces file/reference hygiene on top.

Commit references W2-03-addon-inject, S-03, F-012, TC-SEC-006.
