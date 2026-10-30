# W2-01-addon-server — Wire protocol server: auth, limits, dispatch

| Field | Value |
|---|---|
| Wave | W2 (planes behind contracts; M1–M3) |
| Owner | oxr-w-addon |
| Writes | `addon/openxr_operator/server.gd`, `addon/openxr_operator/tests/` (new) |
| Depends on | W2-01-qa-demo-project (execution harness project) |
| Findings | F-001, F-017, F-027, S-02, S-16; audit TC-SEC-001, TC-SEC-002 |
| Contracts | `docs/contracts/wire-protocol.md`, `addon/openxr_operator/protocol.gd` (read-only) |

## Scope (RPI)

Implement the game-process WebSocket server per the frozen wire contract:

- Bind `127.0.0.1:9099` only. No configuration path may change the bind.
- First frame on every connection MUST be `{"cmd":"auth","token":"<64 hex>","protocol":2}`.
  One attempt, 2 s deadline (`AUTH_DEADLINE_MS`), close 1008 on failure,
  constant-time compare. **Nothing dispatches pre-auth**, including error
  messages that confirm command names.
- Protocol mismatch closes with a clear message (F-027).
- Limits from `protocol.gd`: 1 MiB max inbound frame (close 1009), 4 concurrent
  peers, 50 msgs/s/peer (close 1008), 120 s idle (close 1001).
- Commands: `ping`, `scene_tree`, `capture`, `get_property`, `set_property`,
  `inject`, `restart_scene`, `editor_rescan`. Every request carries `id`;
  every reply echoes it (F-017). Unknown command post-auth → explicit error
  reply, connection stays up.
- Token file (S-02): generate 32 random bytes as 64 hex chars at
  `user://openxr_operator.token` if absent; write with the most restrictive
  permissions the platform allows; document honestly what each platform does
  and does not protect (P3-12: on Windows there is no chmod 0600 — say so).
  Never log the token; the token must not appear in any log or artifact.
- Auth nits documented (S-16): the docs comment in server.gd records the
  one-attempt/2 s/close-1008 behavior as specified, no more, no less.

## Mandatory tests (executed evidence required)

- **TC-SEC-001 (F-001):** unauthenticated command rejected, connection closes.
- **TC-SEC-002 (F-027):** wrong protocol version closes with a clear message.
- W2 exit gate: 1 MiB+1 byte frame → close 1009; 51st message in one second →
  close 1008; 5th concurrent peer rejected; idle 120 s → close 1001 (test may
  use shortened timeouts via test-only constants, stated as such).

Harness: headless self-test under `addon/openxr_operator/tests/` executed
against the demo project (lands with W2-01-qa-demo-project). Until then the
card stays open; parse checks (`godot --headless --check-only`, timeout-wrapped)
run from card start.

## Executed evidence (oxr-w-qa acting on the addon plane per human direction 2026-10-30) — DONE

Delivered: `addon/openxr_operator/server.gd` + `addon/openxr_operator/tests/server_test.gd`
(16 tests), installed into the demo project per the S-05 mapping
(`xcopy addon\openxr_operator demo_project\addons\openxr_operator`).

Executed 2026-10-30, Godot 4.7.1 headless, gdUnit4 v6.2.2
(`-a addon/tests -a addons/openxr_operator/tests -c --ignoreHeadlessMode`),
two consecutive clean runs (logs `runs/w2-01-addon-server/05-full-suite.log`,
`06-final.log`): **20/20 test cases, 0 errors, 0 failures, 0 orphans,
gdUnit4 exit code 0** both times. Python regression: pytest 71 passed,
1 skipped (the marked integration placeholder), `07-pytest.log`.
`gdlint` clean, `gdformat --check` clean (post-format run is the green one).

Mandatory tests:
- **TC-SEC-001 (F-001):** unauthenticated `ping` → no reply dispatched,
  close 1008 ("auth required"). PASSED.
- **TC-SEC-002 (F-027):** `protocol: 99` → clear reply
  `{"error": "protocol mismatch: server speaks protocol 2", ok: false,
  protocol: 2}`, then close 1008. PASSED.
- **W2 exit gate:** 1 MiB+1 byte frame (real contract size) → close 1009;
  rate limit → close 1008 ("rate limit") using the stated test-only knob
  5 msgs/s (contract 50); peer cap rejects the extra peer pre-handshake
  using knob 2 (contract 4); idle → close 1001 using knob 400 ms
  (contract 120000 ms). All PASSED, substitutions stated per the card.
- Also executed: auth ok + F-017 id echo; bad token → close 1008; second
  auth attempt post-auth → close 1008 ("one auth attempt"); auth deadline
  (knob 300 ms) → 1008; scene_tree/get_property/set_property against the
  demo scene; unknown + unregistered command → explicit error, connection
  stays up; bad node path → error reply, no crash; restart_scene without a
  current scene → loud named error.

Design notes (executed findings, recorded for the wave):
- Replies are deferred-close flushed: a close requested the same frame as a
  reply drops the reply on Godot 4.7.1; `_close` defers one poll cycle.
- Godot's JSON parser widens all numbers to float; `_reply` re-narrows
  integral ids so the wire carries `"id":41`, not `41.0`.
- gdUnit4 v6.2.2 CI runner is fail-fast by default (reproduced with a probe
  suite); full-suite runs need `-c`. Escalated for CI.
- Token: generated at `user://openxr_operator.token` (32 random bytes via
  `Crypto.generate_random_bytes`, 64 hex), never logged; 0600 request is a
  no-op on Windows — documented in the module docstring (P3-12), S-16 auth
  nits documented verbatim.

Commit references W2-01-addon-server, F-001, F-017, F-027, S-02, S-16,
TC-SEC-001, TC-SEC-002.

## Done when

All tests above executed green, gdlint/gdformat clean, commit(s) reference
`W2-01-addon-server` and finding ids, evidence pasted into this card, card
moved to `swarm/done/`.
