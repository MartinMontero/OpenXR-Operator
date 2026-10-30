## Editor-side capture for "openxr_operator:*" (S-07 fixture).
## _capture receives messages from debugged game processes; rescan triggers
## an editor filesystem scan and acks on the same channel.
@tool
extends EditorDebuggerPlugin


func _has_capture(capture: String) -> bool:
	return capture == "openxr_operator"


func _capture(message: String, data: Array, session_id: int) -> bool:
	if message != "openxr_operator:rescan":
		return false
	print("oxr_debug_probe: rescan requested by session ", session_id)
	var scanned := false
	if OS.has_feature("editor"):
		var fs := EditorInterface.get_resource_filesystem()
		if fs != null:
			fs.scan()
			scanned = true
	print("oxr_debug_probe: scanned=", scanned, " sending ack")
	var session := get_session(session_id)
	if session != null and session.is_active():
		session.send_message("openxr_operator:ack",
			["rescan", scanned, Time.get_ticks_msec()])
		print("oxr_debug_probe: ack sent")
	else:
		print("oxr_debug_probe: session not active, ack NOT sent")
	return true
