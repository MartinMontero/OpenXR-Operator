## Editor bridge — EngineDebugger channel endpoint (wire command
## "editor_rescan"). Card: W2-04-addon-debugger-matrix (F-011, S-07).
##
## F-011: editor-side work goes over the EngineDebugger capture channel
## ("openxr_operator:*", see protocol.gd DEBUGGER_CAPTURE), never
## EditorInterface from the game process. This module is the game-process
## endpoint: it forwards editor_rescan to the editor and reports the ack.
##
## Availability (S-07 matrix — the full measured matrix lives in
## addon/openxr_operator/DEBUGGER.md; every cell CONFIRMED by execution or
## marked UNTESTED with the reason):
##   - Editor run (game with --remote-debug to a listening editor): channel
##     active; round trip executed.
##   - Debug export without a debugger attached / any non-debugged process:
##     EngineDebugger inactive; editor_rescan fails loudly with a named
##     error (never a silent no-op).
##   - Release export: same inactive path (release builds strip debugger
##     activity); binary-level cell UNTESTED on this host (no export
##     templates installed) — the code path exercised is identical.
extends Node

const Protocol = preload("res://addons/openxr_operator/protocol.gd")

## Test-only knob: how long editor_rescan waits for the editor ack before
## failing loudly. Code-only, never from the wire.
var ack_timeout_ms := 5000

var _last_ack: Array = []
var _ack_seq := 0


func _ready() -> void:
	_game_log("bridge _ready: debugger active=%s" % EngineDebugger.is_active())
	if EngineDebugger.is_active():
		EngineDebugger.register_message_capture(Protocol.DEBUGGER_CAPTURE, _on_editor_message)
		_game_log("bridge: capture registered")


func register_on(server: Node) -> void:
	server.register_command("editor_rescan", handle_editor_rescan)


func _game_log(line: String) -> void:
	# Editor-run games have stdout captured by the editor UI; persist
	# diagnostics to a file for the S-07 evidence trail.
	var path := "user://oxr_game_debug.log"
	# READ_WRITE does not create a missing file; open WRITE once first.
	if not FileAccess.file_exists(path):
		var fw := FileAccess.open(path, FileAccess.WRITE)
		if fw != null:
			fw.close()
	var f := FileAccess.open(path, FileAccess.READ_WRITE)
	if f == null:
		return
	f.seek_end()
	f.store_line("%d %s" % [Time.get_ticks_msec(), line])
	f.close()


func _on_editor_message(message: String, data: Array) -> bool:
	_game_log("bridge _on_editor_message: %s %s" % [message, str(data)])
	# Executed finding (2026-10-30): the game-side capture receives the
	# message with the capture prefix STRIPPED ("ack"), while the editor
	# side EditorDebuggerPlugin._capture receives the full prefixed form
	# ("openxr_operator:rescan"). Accept both.
	if message == "ack" or message == Protocol.DEBUGGER_CAPTURE + ":ack":
		_last_ack = data
		_ack_seq += 1
		return true
	return false


## True when the editor debugger channel is live (debug/editor run).
func channel_available() -> bool:
	return EngineDebugger.is_active()


func handle_editor_rescan(_msg: Dictionary) -> Dictionary:
	if not channel_available():
		var err := (
			"editor_rescan unavailable: EngineDebugger is inactive "
			+ "(not an editor/debug run; release exports have no editor "
			+ "channel). Failing loudly, never silently (F-011)."
		)
		push_warning("openxr_operator editor_bridge: " + err)
		return {"ok": false, "error": err}
	var seq_before := _ack_seq
	EngineDebugger.send_message(Protocol.DEBUGGER_CAPTURE + ":rescan", [])
	var start := Time.get_ticks_msec()
	while _ack_seq == seq_before and Time.get_ticks_msec() - start < ack_timeout_ms:
		await get_tree().process_frame
	if _ack_seq == seq_before:
		var err := "editor_rescan: no editor ack within %d ms" % ack_timeout_ms
		push_warning("openxr_operator editor_bridge: " + err)
		return {"ok": false, "error": err}
	return {
		"ok": true,
		"delivered": Protocol.DEBUGGER_CAPTURE + ":rescan",
		"ack": _last_ack,
	}
