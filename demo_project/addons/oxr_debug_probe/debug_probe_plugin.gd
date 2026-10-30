## Demo-local editor-side debugger probe (S-07 matrix fixture, W2-04).
## Captures "openxr_operator:*" messages from game processes, performs the
## requested editor-side action (rescan = filesystem scan), and acks back on
## the same channel. This is a DEMO fixture proving channel availability; the
## addon's production editor plugin (plugin.gd/debugger_plugin.gd) is a known
## escalated gap.
##
## For the executed matrix the probe AUTO-PLAYS the demo scene
## (editor-run cell) and quits the editor after a watchdog timeout.
@tool
extends EditorPlugin

var _debugger: EditorDebuggerPlugin
var _t := 0.0
var _played := false
var _session_log_done := false


func _enter_tree() -> void:
	var script: GDScript = load(
		"res://addons/oxr_debug_probe/debug_capture.gd")
	_debugger = script.new()
	add_debugger_plugin(_debugger)
	print("oxr_debug_probe: editor plugin entered, debugger capture registered")
	if OS.get_cmdline_args().has("--oxr-autoplay"):
		_play.call_deferred()


func _exit_tree() -> void:
	if _debugger != null:
		remove_debugger_plugin(_debugger)
		_debugger = null


func _play() -> void:
	print("oxr_debug_probe: auto-playing demo scene (editor-run cell)")
	EditorInterface.play_custom_scene("res://scenes/main.tscn")
	_played = true


func _process(delta: float) -> void:
	if not _played:
		return
	_t += delta
	if _t >= 5.0 and not _session_log_done:
		_session_log_done = true
		for s in _debugger.get_sessions():
			print("oxr_debug_probe: session active=", s.is_active())
	# watchdog: quit the editor 60 s after play so CI never hangs
	if _t >= 120.0:
		print("oxr_debug_probe: watchdog quit")
		get_tree().quit()
