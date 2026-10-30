# Vendored dependencies — demo_project/

Per kit §7.5: Godot addons have no package ecosystem; vendored addons are
pinned by commit and enumerated by hand. osv-scanner does not cover GDScript.

## gdUnit4

| Field | Value |
|---|---|
| Version | v6.2.2 (satisfies S-12: ≥ 6.2.0) |
| Upstream | https://github.com/godot-gdunit-labs/gdUnit4 (formerly MikeSchulze/gdUnit4) |
| Pinned commit | `0127a55f4543dfc24746f6e5c7ba6f94105d51f2` (tag `v6.2.2`, published 2026-10-07) |
| Source zip SHA-256 | `58a391b0c85cbbcf7aeb09b718c8173793d45ab511950cd65eec0183aabf0e50` |
| Licence | MIT (shipped in `addons/gdUnit4/LICENSE`; matches kit §4.2 register row "gdUnit4 v6.x MIT Pass") |
| Vendored path | `demo_project/addons/gdUnit4/` |
| Vendored by | oxr-w-qa, 2026-10-29, W2-01-qa-demo-project |

Retrieval executed:
`curl -sSfL -o gdunit4-v6.2.2.zip https://github.com/godot-gdunit-labs/gdUnit4/archive/0127a55f4543dfc24746f6e5c7ba6f94105d51f2.zip`

Note: `docs/dependency-register.md` does not exist on main (W1 closed without
it landing). The gdUnit4 register entry (S-12) is escalated via
`swarm/requests/` per the W2-01-qa-demo-project card's escalation clause.
