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
