# W2-01-operator-fsguard — Path containment (S-04) with logged rejection

| Field | Value |
|---|---|
| Wave | W2 |
| Owner | oxr-w-operator |
| Writes | `operator/src/openxr_operator/fsguard.py` (new), `operator/tests/test_fsguard.py` (new) |
| Depends on | — |
| Findings | F-003, S-04; audit TC-SEC-003 |
| Contracts | `docs/contracts/` (read-only); kit §6.4 |

## Scope (RPI)

Implement path containment per kit §6.4, **minus the dead symlink check**
(S-04: the check was removed because it raced; the residual TOCTOU window is
documented in the module docstring — what an attacker would need, what still
protects the path, why the check was not load-bearing).

- Resolution root: the launched project's directory, captured at flow start.
- Every path the runner touches (frames to disk, artifacts, logs) resolves
  through the guard.
- Rejections raise a named error **and are logged** (W2 exit gate: traversal
  rejected + logged).

## Mandatory tests (executed evidence required)

- **TC-SEC-003 (F-003):** absolute path, `..` traversal, symlink escape,
  oversize — all raise. Each case asserts both the raise and the log entry.
- AAA form, deterministic, no filesystem fixtures outside tmp_path.

## Constraints

- mypy --strict, ruff clean, pytest green.
- `fsguard.py` is on the security floor: coverage target 100% (audit §4).

## Done when

TC-SEC-003 executed green with log assertions, TOCTOU note in the docstring,
commit(s) reference `W2-01-operator-fsguard`, F-003 and S-04, card moved to
`swarm/done/`.
