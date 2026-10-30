# W2-02-addon-capture: capture command tests (TC-SEC-005 black-frame honesty,
# non-black capture at declared tier, tier honesty).
#
# These tests need REAL rendering (viewport readback); --headless uses the
# dummy RenderingServer and every readback is empty. Run WITHOUT --headless
# (locally: windowed; CI: xvfb-run — escalated in
# swarm/requests/W2-01-qa-register-ci-requests.md). Do not run them headless
# and do not weaken them to pass headless.
extends GdUnitTestSuite

const Server = preload("res://addons/openxr_operator/server.gd")
const Capture = preload("res://addons/openxr_operator/capture.gd")
const Protocol = preload("res://addons/openxr_operator/protocol.gd")
const MainScene = preload("res://scenes/main.tscn")

const URL := "ws://127.0.0.1:9099"
const CAPTURE_DIR := "user://openxr_operator_captures"

var _server: Node
var _capture: Node


func before() -> void:
	# Windowed runs on this host can open occluded/minimized; an
	# unpresented window never emits frame_post_draw. Ask for foreground.
	DisplayServer.window_move_to_foreground()
	# Windowed runs on this host can open occluded/minimized; an
	# unpresented window never emits frame_post_draw. Ask for foreground.
	DisplayServer.window_move_to_foreground()
	# Windowed runs on this host can open occluded/minimized; an
	# unpresented window never emits frame_post_draw. Ask for foreground.
	DisplayServer.window_move_to_foreground()
	# Windowed runs on this host can open occluded/minimized; an
	# unpresented window never emits frame_post_draw. Ask for foreground.
	DisplayServer.window_move_to_foreground()
	# Windowed runs on this host can open occluded/minimized; an
	# unpresented window never emits frame_post_draw. Ask for foreground.
	DisplayServer.window_move_to_foreground()
	# GdUnitCmdTool._initialize() MINIMIZES the window; a minimized window is
	# never presented and RenderingServer.frame_post_draw never fires
	# (executed finding, 2026-10-30). This suite exists to exercise real
	# readback, so restore the window and ask for foreground.
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_move_to_foreground()
	_server = Server.new()
	get_tree().root.add_child(_server)
	assert_bool(_server.is_listening()).is_true()
	_capture = Capture.new()
	get_tree().root.add_child(_capture)
	_capture.register_on(_server)
	# This host can take >100 s to present the first frame (executed
	# finding); give captures a generous budget. Code-side knob.
	_capture.frame_timeout_ms = 180000
	# Warm-up: confirm the host actually presents before any capture test
	# runs; if it cannot, fail HERE with a named environment error instead of
	# mysteriously inside a capture test.
	var fired := [false]  # array cell: lambdas capture locals by value
	var cb := func() -> void: fired[0] = true
	RenderingServer.frame_post_draw.connect(cb, CONNECT_ONE_SHOT)
	var start := Time.get_ticks_msec()
	while not fired[0] and Time.get_ticks_msec() - start < 180000:
		await get_tree().process_frame
	assert_bool(fired[0]).is_true().append_failure_message(
		(
			"host did not present a frame within 180 s; this suite needs a "
			+ "real display (CI: xvfb-run)"
		)
	)


func after() -> void:
	_capture.free()
	_server.free()


func after_test() -> void:
	for i in 5:
		await get_tree().process_frame


# -- helpers (same wire pattern as server_test.gd) ------------------------------


func _connect_authed() -> WebSocketPeer:
	var c := WebSocketPeer.new()
	assert_int(c.connect_to_url(URL)).is_equal(OK)
	var deadline := Time.get_ticks_msec() + 3000
	while (
		c.get_ready_state() == WebSocketPeer.STATE_CONNECTING and Time.get_ticks_msec() < deadline
	):
		c.poll()
		await get_tree().process_frame
	assert_int(c.get_ready_state()).is_equal(WebSocketPeer.STATE_OPEN)
	var f := FileAccess.open(Protocol.TOKEN_PATH, FileAccess.READ)
	var token := f.get_as_text().strip_edges()
	f.close()
	c.send_text(JSON.stringify({"cmd": "auth", "id": 1, "token": token, "protocol": 2}))
	c.poll()
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", false)).is_true()
	return c


func _recv_dict(c: WebSocketPeer, max_ms := 5000) -> Dictionary:
	var deadline := Time.get_ticks_msec() + max_ms
	while Time.get_ticks_msec() < deadline:
		c.poll()
		if c.get_available_packet_count() > 0:
			var parsed: Variant = JSON.parse_string(c.get_packet().get_string_from_utf8())
			if parsed is Dictionary:
				return parsed
			return {}
		await get_tree().process_frame
	return {}


func _capture_dir_files() -> int:
	var dir := DirAccess.open(CAPTURE_DIR)
	if dir == null:
		return 0
	var count := 0
	for file in dir.get_files():
		if file.ends_with(".png"):
			count += 1
	return count


func _render_frames(n: int) -> void:
	# Wall-clock bounded: never hang the suite if presentation stalls.
	var deadline := Time.get_ticks_msec() + 20000
	for i in n:
		await get_tree().process_frame
		if Time.get_ticks_msec() > deadline:
			break


func test_tc_sec_005_black_frame_reported_never_artifact() -> void:
	var black: Node = load("res://scenes/black.tscn").instantiate()
	get_tree().root.add_child(black)
	auto_free(black)
	await _render_frames(3)
	var files_before := _capture_dir_files()
	var c := await _connect_authed()
	c.send_text(JSON.stringify({"cmd": "capture", "id": 2, "label": "black-test"}))
	c.poll()
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", false)).is_true()
	var frame: Dictionary = reply.get("frame", {})
	# Reported as black — and NEVER written to disk as a screenshot.
	assert_bool(frame.get("black", false)).is_true()
	assert_bool(frame.get("black_frame", false)).is_true()
	assert_bool(frame.has("path")).is_false()
	assert_str(str(frame.get("tier", ""))).is_equal("t3")
	assert_int(_capture_dir_files()).is_equal(files_before)


func test_non_black_capture_at_declared_tier() -> void:
	var main: Node = MainScene.instantiate()
	get_tree().root.add_child(main)
	auto_free(main)
	await _render_frames(3)
	var c := await _connect_authed()
	c.send_text(JSON.stringify({"cmd": "capture", "id": 2, "label": "main-shot", "tier": "t3"}))
	c.poll()
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", false)).is_true()
	var frame: Dictionary = reply.get("frame", {})
	# Tier on the artifact equals the flow's declaration (D-04 honesty).
	assert_str(str(frame.get("tier", ""))).is_equal("t3")
	assert_bool(frame.get("black", false)).is_false()
	var path := str(frame.get("path", ""))
	assert_str(path).is_not_empty()
	assert_bool(FileAccess.file_exists(path)).is_true()
	var bytes := FileAccess.get_file_as_bytes(path)
	assert_int(bytes.size()).is_greater(100)
	assert_str(FileAccess.get_sha256(path)).is_equal(str(frame.get("sha256")))
	assert_int(int(frame.get("width", 0))).is_greater(0)
	assert_int(int(frame.get("height", 0))).is_greater(0)


func test_tier_report_is_actual_not_echoed() -> void:
	var main: Node = MainScene.instantiate()
	get_tree().root.add_child(main)
	auto_free(main)
	await _render_frames(3)
	var c := await _connect_authed()
	# Request t2 against a desktop harness: the engine must report t3 (what
	# it actually produced); the operator-side verifier rejects the mismatch.
	c.send_text(JSON.stringify({"cmd": "capture", "id": 2, "label": "tier-check", "tier": "t2"}))
	c.poll()
	var reply := await _recv_dict(c)
	var frame: Dictionary = reply.get("frame", {})
	assert_str(str(frame.get("tier", ""))).is_equal("t3")


func test_bad_capture_label_rejected() -> void:
	var c := await _connect_authed()
	c.send_text(JSON.stringify({"cmd": "capture", "id": 2, "label": "../escape"}))
	c.poll()
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("bad capture label")
