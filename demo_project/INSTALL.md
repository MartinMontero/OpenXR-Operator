# INSTALL.md — demo_project (executed, S-05 mapping part)

Every step below was executed by oxr-w-qa on 2026-10-29 (Windows 11, cmd).
This file is the *mapping* proof for S-05; the end-user runbook is W5 scope.

## Mapping proven

```
repo:  addon/openxr_operator/            (MIT, LICENSES/MIT.txt applies)
  -->  demo_project/addons/openxr_operator/

vendor: gdUnit4 v6.2.2 @ 0127a55f4543dfc24746f6e5c7ba6f94105d51f2 (MIT)
  -->  demo_project/addons/gdUnit4/
```

The mapping the end-user runbook will automate: **copy `addon/openxr_operator/`
into the target project's `addons/` directory, then enable the plugin in
`project.godot` `[editor_plugins]`.** No installer, no registry writes, nothing
outside the project tree — same shape as the kit's layer constraint (no
system-wide install), one directory weaker.

## Executed steps

1. `xcopy /E /I /Q addon\openxr_operator demo_project\addons\openxr_operator`
   → 2 files copied (`plugin.cfg`, `protocol.gd`).
2. Downloaded gdUnit4 source zip pinned to commit
   `0127a55f4543dfc24746f6e5c7ba6f94105d51f2` (tag v6.2.2); SHA-256 verified
   (`58a391b0…bf0e50`, see `VENDORED.md`); extracted; copied
   `addons/gdUnit4/` → `demo_project/addons/gdUnit4/` (272 files).
3. Wrote `project.godot` with
   `[editor_plugins] enabled=PackedStringArray("res://addons/gdUnit4/plugin.cfg", "res://addons/openxr_operator/plugin.cfg")`.
4. `godot --headless --path demo_project --import` → rc=0
   (evidence: `runs/w2-01/01-import.log`).
5. `godot --headless --path demo_project res://scenes/main.tscn --quit-after 5`
   → rc=0, no errors (`runs/w2-01/02-scene-load.log`).

## Known gap (CONFIRMED, escalated)

`addons/openxr_operator/plugin.cfg` declares `script="plugin.gd"`, but
`plugin.gd` does not exist in `addon/openxr_operator/` on main, and no W2
card schedules it. The addon is therefore **installed and listed as enabled**,
but the editor plugin cannot actually load; the import log shows:

```
ERROR: Attempt to open script 'res://addons/openxr_operator/plugin.gd' resulted in error 'File not found'.
ERROR: Failed loading resource: res://addons/openxr_operator/plugin.gd.
```

This is non-fatal (import and scene loads exit rc=0) and does not affect
gdUnit4 or scene tests, but full "enabled" status is BLOCKED on the addon
plane delivering `plugin.gd`. Escalated via
`swarm/requests/W2-01-qa-register-ci-requests.md`.

## Re-run the harness

```
godot --headless --path demo_project --import
godot --headless --path demo_project -s addons/gdUnit4/bin/GdUnitCmdTool.gd \
  -a addon/tests -rd runs/<run>/gdunit4-reports --ignoreHeadlessMode
```

`--ignoreHeadlessMode` is required: gdUnit4 v6.2.2 refuses plain `--headless`
with exit 103 (executed finding, `runs/w2-01/` first attempt). `-rd` is
relative to the project path — use an absolute path to keep reports outside
`demo_project/`. The kit CI snippet (§7.2) predates both facts and must be
updated — included in the same escalation request.
