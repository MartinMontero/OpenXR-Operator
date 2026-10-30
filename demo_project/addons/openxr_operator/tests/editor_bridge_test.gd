# W2-04-addon-debugger-matrix: unavailability path (F-011 loud failure).
# Headless/no-debugger process == the same EngineDebugger-inactive code path
# a release export hits. The editor-run round trip is executed separately
# (see card evidence / addon/openxr_operator/DEBUGGER.md).
extends GdUnitTestSuite

const Server = preload("res://addons/openxr_operator/server.gd")
const Bridge = preload("res://addons/openxr_operator/editor_bridge.gd")
const Protocol = preload("res://addons/openxr_operator/protocol.gd")

const URL := "ws://127.0.0.1:9099"

var _server: Node
var _bridge: Node


func before() -> void:
	_server = Server.new()
	get_tree().root.add_child(_server)
	assert_bool(_server.is_listening()).is_true()
	_bridge = Bridge.new()
	get_tree().root.add_child(_bridge)
	_bridge.register_on(_server)


func after() -> void:
	_bridge.free()
	_server.free()


func after_test() -> void:
	for i in 5:
		await get_tree().process_frame


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


func test_channel_unavailable_headless_process() -> void:
	# No debugger attached to this test process.
	assert_bool(_bridge.channel_available()).is_false()
	assert_bool(EngineDebugger.is_active()).is_false()


func test_editor_rescan_fails_loudly_when_unavailable() -> void:
	var c := await _connect_authed()
	c.send_text(JSON.stringify({"cmd": "editor_rescan", "id": 2}))
	c.poll()
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("EngineDebugger is inactive")
	# Connection stays up.
	c.send_text(JSON.stringify({"cmd": "ping", "id": 3}))
	c.poll()
	assert_bool((await _recv_dict(c)).get("ok", false)).is_true()


func test_unavailable_rescan_is_logged() -> void:
	await (
		assert_error(func() -> void: _bridge.handle_editor_rescan({"id": 9}))
		. is_push_warning(
			(
				"openxr_operator editor_bridge: editor_rescan unavailable: "
				+ "EngineDebugger is inactive (not an editor/debug run; release "
				+ "exports have no editor channel). Failing loudly, never silently "
				+ "(F-011)."
			)
		)
	)
