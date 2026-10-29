# W2-02-addon-capture — T2/T3 capture with black-frame honesty

| Field | Value |
|---|---|
| Wave | W2 |
| Owner | oxr-w-addon |
| Writes | `addon/openxr_operator/capture.gd`, `addon/openxr_operator/tests/` |
| Depends on | W2-01-addon-server, W2-01-qa-demo-project |
| Findings | F-010, S-02 (n/a), D-04 tier honesty; audit TC-SEC-005 |
| Contracts | `docs/contracts/wire-protocol.md` (frames-to-disk channel) |

## Scope (RPI)

Implement the `capture` command at the v1 tiers (D-04: T2 mirror viewport and
T3 desktop harness only; A3 is the injection floor):

- T2: mirror viewport readback, `await RenderingServer.frame_post_draw`
  before every readback.
- Black-frame detection on every capture: an all-black (or single-colour)
  frame is detected and **reported**, never returned as a silent screenshot.
  The reply carries `black_frame: true` and no path, or the command fails
  loudly — pick one, document it.
- Tier is recorded on every frame artifact (D-04 tier honesty: every run
  artifact and report carries its tier).
- Frames go to disk; the channel carries `{path, tier, sha256, ...}`, never
  base64 (wire contract §2.5).
- Disclosure (D-04 consequence): F-010 (exact composited-frame capture) is
  never fully resolved in v1. The capture module's docstring states plainly
  what T2 proves and what it does not.

## Mandatory tests (executed evidence required)

- **TC-SEC-005 (F-010):** black frame detected + reported, never returned as
  a screenshot. Fixture: a scene rendering pure black must produce the
  reported-black outcome, not an image artifact.
- W2 exit gate: non-black capture at declared tier — a rendered frame from
  the demo project is non-black and its artifact metadata tier equals the
  flow's declared tier.

## Done when

Tests executed green, evidence pasted, commit(s) reference
`W2-02-addon-capture` and F-010, card moved to `swarm/done/`.
