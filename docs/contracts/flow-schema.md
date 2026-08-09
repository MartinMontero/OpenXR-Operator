# Flow YAML contract (FROZEN after W1 — orchestrator-owned)

Header: project, scene, capture_tier (auto|t1|t2|t3), inject_tier (auto|a1|a2|a3),
capabilities (deny-all default: everything not listed is denied), env. Then `---`
and an ordered command list.

Commands: launch, settle (never sleep — sleep is not in the vocabulary),
assert_visible, assert_property, move_controller, press, capture, run_flow
(with when), repeat, wait_until.

Rules (build kit v2.0 section 5.4, v3.0 S-15):
- Flows validate against the JSON Schema before any step executes.
- settle validates on_timeout at parse time; invalid values are REJECTED,
  never silently coerced (S-15).
- Zero selector matches is an error unless optional; multiple matches without
  an index is an error; every resolution is logged with the candidate set.
