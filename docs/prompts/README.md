# Agent prompts

All swarm prompts are present. One manual addition remains:

- `../BUILD_KIT_v3.pdf` — place the build-kit PDF in `docs/` (binary; commit
  locally). P-0 lists it as canonical input #1; the swarm is blocked without it.

## Orchestration order

1. Paste `P-0-orchestrator.md` into the orchestrator session
   (`/title oxr-orchestrator`) at the repository root. It runs W0/W1 itself and
   writes task cards to `swarm/tasks/`.
2. As the orchestrator opens cards per wave, paste each worker prompt into its
   own titled session: `P-1-worker-addon.md` (`/title oxr-w-addon`),
   `P-2-worker-operator.md` (`/title oxr-w-operator`), `P-3-worker-ui.md`
   (`/title oxr-w-ui`), `P-4-worker-layer.md` (`/title oxr-w-layer`, gated on
   human decision D-04), `P-5-worker-qa.md` (`/title oxr-w-qa`).
3. `audit-prompt-v3.md` and `implementation-prompt-v2.md` are the two loop
   prompts: the audit was already executed (its findings and suspect
   dispositions are baked into the wave plan and the P-prompts);
   `implementation-prompt-v2.md` is the single-session fallback if the swarm
   is ever scaled down to one agent.

Workers read only their own cards (`swarm/tasks/W*-<role>-*.md`) plus their
contract files. Contract changes go through `swarm/requests/`.
