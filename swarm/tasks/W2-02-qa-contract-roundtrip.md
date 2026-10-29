# W2-02-qa-contract-roundtrip — Fake engine ↔ fake agent; W2 exit-gate replay

| Field | Value |
|---|---|
| Wave | W2 (last card chronologically) |
| Owner | oxr-w-qa |
| Writes | `flows/`, `runs/`, `VERIFICATION.md` |
| Depends on | W2-01-addon-server, W2-02-addon-capture, W2-03-addon-inject, W2-01-operator-fsguard, W2-02-operator-driver, W2-01-qa-demo-project |
| Findings | W2 exit gate (PLAN §2); P-5 contract-test mandate |

## Scope (RPI)

Make the W2 exit gate executable end-to-end. Every line below is executed,
with evidence — this card is the wave's proof, not a restatement of it:

1. Unauth command closes connection (replays TC-SEC-001 against the real pair).
2. Wrong protocol version closes with a clear message (TC-SEC-002 replay).
3. 1 MiB+1 frame rejected, close 1009.
4. 51st message in one second closes the peer, close 1008.
5. Non-black capture at declared tier — artifact on disk, `{path, tier,
   sha256}` verified, tier equals the flow's declaration.
6. Bogus tracker raises — named error on the wire, logged by the operator.
7. Traversal rejected AND logged — a `../` artifact path through the runner
   fails with the fsguard error and appears in the log.

Plus the P-5 standing items as they become executable: bad Origin rejected;
unbypassable approval attempted (stub until W4 wires the approval record —
label it as such, do not fake it).

## Method

Fake engine ↔ fake agent round-trip first (no Godot, no model — deterministic
sockets), then the real addon + real driver against the demo project,
model disabled, T3. Two consecutive clean full runs before the wave is called
done (kit §6.1 loop). Results recorded in VERIFICATION.md with per-step
capture tier, injection tier, and settle outcome.

## Done when

All seven exit-gate lines executed with pasted evidence, two consecutive clean
runs recorded in VERIFICATION.md, commit(s) reference
`W2-02-qa-contract-roundtrip`, card moved to `swarm/done/`. W2 cannot be
called done without this card.
