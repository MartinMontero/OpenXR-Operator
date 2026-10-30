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

## Executed evidence (oxr-w-qa on the addon plane per human direction 2026-10-30) — DONE

Delivered: addon/openxr_operator/capture.gd + addon/openxr_operator/tests_render/capture_test.gd;
server.gd gained an async dispatch queue (capture awaits frame_post_draw; Godot 4.7
parse-enforces await on coroutines, so dispatch drains via a dynamic Callable).

Executed 2026-10-30, Godot 4.7.1, gdUnit4 v6.2.2, windowed (real GPU readback) with
--audio-driver Dummy, TWO consecutive clean runs (runs/w2-02-addon-capture/14-render-run1.log,
15-render-run2.log): 4/4 test cases, 0 errors/failures/orphans, exit code 0.

- TC-SEC-005 (F-010): black.tscn fixture renders pure black; capture reply is
  {ok: true, frame: {tier: t3, black: true, black_frame: true}} with NO path, and the
  capture dir file count is unchanged — reported, never an artifact. PASSED.
- W2 exit gate non-black capture at declared tier: main.tscn renders; artifact on disk
  with {path, tier: t3, sha256, width, height, frame_id}; sha256 recomputed from the
  bytes on disk matches; tier equals the declared t3. PASSED.
- Tier honesty: requesting t2 on a desktop harness reports t3 (actual, from XRServer
  state) — never echoed. PASSED. Operator-side verifier rejects the mismatch (driver
  tests, oxr-w-remote, already green).
- Label sanitization: ../escape rejected with a named error before any disk write. PASSED.
- Independent re-verification over the real wire via a custom runner
  (runs/w2-02-addon-capture/render_check.gd, 17/17 checks PASS, log 12-render-check.log).
- Headless regression (server + harness): 20/20, exit 0 (16-headless-final.log).
  pytest: 71 passed, 1 skipped (marked integration placeholder). gdlint/gdformat clean.

Executed findings folded into docs/escalation:
- gdUnit4 CI runner minimizes its window at birth (GdUnitCmdTool._initialize); the render
  suite restores it and fails loudly if the host cannot present. CI needs xvfb-run
  (escalated in swarm/requests/W2-01-qa-register-ci-requests.md section 2b).
- GDScript lambdas capture locals by value: a watchdog flag must ride in an array cell;
  a plain bool silently never updates (root cause of several red runs during bring-up).
- Hosts without an audio device stall the main loop on WASAPI retries; --audio-driver
  Dummy fixes it.
- capture.gd never blocks the command queue: bounded frame wait, then a named error.

F-010/D-04 disclosure is in the capture.gd module docstring verbatim (T2/T3 prove the
composited viewport pixels on this machine, not the headset image; exact composited-frame
capture unresolved in v1).

Commit references W2-02-addon-capture, F-010, TC-SEC-005, D-04.
