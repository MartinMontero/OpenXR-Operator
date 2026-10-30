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

## Evidence (executed 2026-10-29, Windows host, Python 3.13.14, operator/.venv)

TC-SEC-003 — all four mandatory cases assert BOTH the raise and the log entry:

```
tests/test_fsguard.py::test_tc_sec_003_absolute_path_rejected_and_logged PASSED
tests/test_fsguard.py::test_tc_sec_003_parent_traversal_rejected_and_logged PASSED
tests/test_fsguard.py::test_tc_sec_003_backslash_traversal_rejected_and_logged PASSED
tests/test_fsguard.py::test_tc_sec_003_symlink_escape_rejected_and_logged PASSED
tests/test_fsguard.py::test_tc_sec_003_oversize_content_rejected_and_logged PASSED
21 passed in 0.27s
```

- Symlink case: host lacks the symlink privilege (CONFIRMED — WinError 1314
  reproduced standalone), so the test exercised the documented fallback: a
  directory junction, the same resolve()-followed escape vector (CONFIRMED —
  junction resolves outside root, `is_relative_to` False). On POSIX CI the
  real `os.symlink` path executes.
- Log assertions via `caplog` on logger `openxr_operator.fsguard`: every
  rejection logs `fsguard rejected path: reason=... attempted=...` at WARNING
  before raising `PathRejected` (log-then-raise in `_reject`).
- Oversize case also asserts nothing was written; traversal case asserts the
  escape target does not exist.

Gates (all executed, this tree):

```
ruff format --check .   → 13 files already formatted
ruff check .            → All checks passed!
mypy --strict src       → Success: no issues found in 8 source files
pytest -q               → 52 passed in 3.65s
```

Coverage (audit §4 target 100% for the security floor): stdlib `trace`
line-coverage over `openxr_operator/fsguard.py` under the test module → zero
`>>>>>` missed-line markers = 100% line coverage (no coverage package in dev
deps; measured with the stdlib). 21 tests total incl. positive-path,
suffix-allowlist, empty/padded, contained-symlink, and missing-root cases.

TOCTOU note (S-04): in the `fsguard.py` module docstring — why the kit's
`target.is_symlink()` check was dead code (post-`resolve()` the leaf is never
a symlink), why it was not load-bearing (a post-check swap defeats it too),
what the residual window requires (a second process with write access inside
the project root racing one write), and what still protects the path (OS
filesystem jail §3.4/D-05, diff-then-approve, logged rejections).

Repo-hygiene note: a concurrent orchestrator commit (8cfc4e2, `git add -A`)
swept the then-uncommitted `fsguard.py` into its 526-file commit. Its content
matches this card's implementation except one `ruff format` line-wrap, which
this card's closing commit applies together with the tests.
