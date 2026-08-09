# Swarm status

| Role | Session title | State | Current task | Updated |
|---|---|---|---|---|
| orchestrator | oxr-orchestrator | awaiting start | — | — |
| engine worker | oxr-w-addon | idle | — | — |
| agent-core worker | oxr-w-operator | idle | — | — |
| ui worker | oxr-w-ui | idle | — | — |
| layer worker | oxr-w-layer | gated on D-04 | — | — |
| qa worker | oxr-w-qa | idle | — | — |

Coordination rules: exclusive file ownership per role; contract changes via
swarm/requests/ ruled on by the orchestrator (recorded in swarm/decisions/);
task cards in swarm/tasks/ move to swarm/done/ only with executed evidence.
