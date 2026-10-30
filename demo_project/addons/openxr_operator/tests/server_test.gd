# W2-01-addon-server: wire protocol v2 server tests (TC-SEC-001, TC-SEC-002,
# W2 exit-gate limits). Executed headless via gdUnit4 against the demo
# project install (addons/openxr_operator == addon/openxr_operator, S-05).
#
# Exit-gate limits use shortened TEST-ONLY values (the card states this is
# allowed): the server exposes code-only knobs defaulting to the contract
# values in protocol.gd; tests override them and say so per test. The 1 MiB
# frame test uses the real contract size — no substitution.
extends GdUnitTestSuite

const Server := preload("res://addons/openxr_operator/server.gd")
const Protocol = preload("res://addons/openxr_operator/protocol.gd")

const URL := "ws://127.0.0.1:9099"
const MAIN_SCENE := "res://scenes/main.tscn"

var _server: Node


func before() -> void:
	_server = Server.new()
	get_tree().root.add_child(_server)
	assert_bool(_server.is_listening()).is_true().append_failure_message(
		"server did not bind %s:%d" % [Protocol.BIND, Protocol.PORT]
	)


func after() -> void:
	_server.free()
	_server = null


func before_test() -> void:
	# Restore contract defaults; individual tests override and say so.
	_server.max_frame_bytes = Protocol.MAX_FRAME_BYTES
	_server.max_peers = Protocol.MAX_PEERS
	_server.max_msgs_per_sec = Protocol.MAX_MSGS_PER_SEC
	_server.auth_deadline_ms = Protocol.AUTH_DEADLINE_MS
	_server.idle_timeout_ms = Protocol.IDLE_TIMEOUT_MS


func after_test() -> void:
	await _pump(5)  # let close handshakes settle so peers drain
	assert_int(_server._peers.size()).is_equal(0).append_failure_message("peer leaked across tests")


# -- client helpers -----------------------------------------------------------


func _token() -> String:
	var f := FileAccess.open(Protocol.TOKEN_PATH, FileAccess.READ)
	assert_object(f).is_not_null()
	return f.get_as_text().strip_edges()


func _connect_client() -> WebSocketPeer:
	var c := WebSocketPeer.new()
	c.inbound_buffer_size = 3 * 1024 * 1024
	c.outbound_buffer_size = 3 * 1024 * 1024
	assert_int(c.connect_to_url(URL)).is_equal(OK)
	var deadline := Time.get_ticks_msec() + 3000
	while (
		c.get_ready_state() == WebSocketPeer.STATE_CONNECTING and Time.get_ticks_msec() < deadline
	):
		c.poll()
		await get_tree().process_frame
	assert_int(c.get_ready_state()).is_equal(WebSocketPeer.STATE_OPEN).append_failure_message(
		"client never reached STATE_OPEN"
	)
	return c


func _pump(frames: int) -> void:
	for i in frames:
		await get_tree().process_frame


func _send(c: WebSocketPeer, msg: Dictionary) -> void:
	assert_int(c.send_text(JSON.stringify(msg))).is_equal(OK)
	c.poll()


func _recv_dict(c: WebSocketPeer, max_ms := 3000) -> Dictionary:
	var deadline := Time.get_ticks_msec() + max_ms
	while Time.get_ticks_msec() < deadline:
		c.poll()
		if c.get_available_packet_count() > 0:
			var raw := c.get_packet().get_string_from_utf8()
			var parsed: Variant = JSON.parse_string(raw)
			if parsed is Dictionary:
				return parsed
			return {}
		await get_tree().process_frame
	return {}


func _await_close(c: WebSocketPeer, max_ms := 5000) -> int:
	var deadline := Time.get_ticks_msec() + max_ms
	while Time.get_ticks_msec() < deadline:
		c.poll()
		if c.get_ready_state() == WebSocketPeer.STATE_CLOSED:
			return c.get_close_code()
		await get_tree().process_frame
	return -1


func _auth(c: WebSocketPeer, id := 1, protocol := 2, token := "") -> Dictionary:
	_send(
		c,
		{
			"cmd": "auth",
			"id": id,
			"token": token if token else _token(),
			"protocol": protocol,
		}
	)
	return await _recv_dict(c)


# -- TC-SEC-001 / TC-SEC-002 ----------------------------------------------------


func test_tc_sec_001_unauthenticated_command_closes_without_reply() -> void:
	var c := await _connect_client()
	_send(c, {"cmd": "ping", "id": 1})
	# No reply may be dispatched pre-auth (F-001: nothing confirms command
	# names), then the connection closes 1008.
	var code := await _await_close(c)
	assert_int(code).is_equal(1008)
	assert_str(c.get_close_reason()).is_equal("auth required")


func test_tc_sec_002_wrong_protocol_version_closes_with_clear_message() -> void:
	var c := await _connect_client()
	var reply: Dictionary = await _auth(c, 1, 99)
	# F-027: a clear message on the auth reply, then close 1008.
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("protocol mismatch")
	assert_int(int(reply.get("protocol", 0))).is_equal(Protocol.PROTOCOL_VERSION)
	var code := await _await_close(c)
	assert_int(code).is_equal(1008)


func test_auth_succeeds_and_echoes_id() -> void:
	var c := await _connect_client()
	var reply: Dictionary = await _auth(c, 41)
	assert_bool(reply.get("ok", false)).is_true()
	assert_int(int(reply.get("id", -1))).is_equal(41)  # F-017 id echo
	assert_int(int(reply.get("protocol", 0))).is_equal(Protocol.PROTOCOL_VERSION)


func test_bad_token_closes_1008() -> void:
	var c := await _connect_client()
	var reply: Dictionary = await _auth(c, 1, 2, "f".repeat(64))
	assert_bool(reply.get("ok", true)).is_false()
	assert_int(await _await_close(c)).is_equal(1008)


func test_second_auth_attempt_rejected() -> void:
	var c := await _connect_client()
	var reply: Dictionary = await _auth(c)
	assert_bool(reply.get("ok", false)).is_true()
	_send(c, {"cmd": "auth", "id": 2, "token": _token(), "protocol": 2})
	assert_int(await _await_close(c)).is_equal(1008)
	assert_str(c.get_close_reason()).is_equal("one auth attempt")


func test_auth_deadline_closes_1008() -> void:
	# TEST-ONLY shortened deadline: 300 ms instead of the contract 2000 ms
	# (protocol.gd AUTH_DEADLINE_MS), per the card's test-only-constants rule.
	_server.auth_deadline_ms = 300
	var c := await _connect_client()
	assert_int(await _await_close(c)).is_equal(1008)
	assert_str(c.get_close_reason()).is_equal("auth deadline")


# -- W2 exit gate: limits --------------------------------------------------------


func test_oversize_frame_closes_1009() -> void:
	# Real contract size: MAX_FRAME_BYTES + 1, no substitution.
	var c := await _connect_client()
	var reply: Dictionary = await _auth(c)
	assert_bool(reply.get("ok", false)).is_true()
	assert_int(c.send_text("x".repeat(Protocol.MAX_FRAME_BYTES + 1))).is_equal(OK)
	c.poll()
	assert_int(await _await_close(c)).is_equal(1009)


func test_rate_limit_closes_1008() -> void:
	# TEST-ONLY shortened limit: 5 msgs/s instead of the contract 50
	# (MAX_MSGS_PER_SEC), per the card's test-only-constants rule.
	_server.max_msgs_per_sec = 5
	var c := await _connect_client()
	await _auth(c)  # message 1
	for i in 6:  # messages 2..7; the 6th within the window trips the limit
		_send(c, {"cmd": "ping", "id": 100 + i})
	assert_int(await _await_close(c)).is_equal(1008)
	assert_str(c.get_close_reason()).is_equal("rate limit")


func test_peer_cap_rejects_extra_peer() -> void:
	# TEST-ONLY shortened cap: 2 instead of the contract 4 (MAX_PEERS).
	_server.max_peers = 2
	var c1 := await _connect_client()
	var c2 := await _connect_client()
	await _auth(c1)
	await _auth(c2)
	var c3 := WebSocketPeer.new()
	assert_int(c3.connect_to_url(URL)).is_equal(OK)
	var deadline := Time.get_ticks_msec() + 3000
	while (
		Time.get_ticks_msec() < deadline and c3.get_ready_state() == WebSocketPeer.STATE_CONNECTING
	):
		c3.poll()
		await get_tree().process_frame
	# Rejected pre-handshake: never OPEN.
	assert_int(c3.get_ready_state()).is_not_equal(WebSocketPeer.STATE_OPEN)


func test_idle_timeout_closes_1001() -> void:
	# TEST-ONLY shortened idle: 400 ms instead of the contract 120000 ms
	# (IDLE_TIMEOUT_MS), per the card's test-only-constants rule.
	_server.idle_timeout_ms = 400
	var c := await _connect_client()
	await _auth(c)
	assert_int(await _await_close(c)).is_equal(1001)
	assert_str(c.get_close_reason()).is_equal("idle timeout")


# -- dispatch against the demo scene ---------------------------------------------


func _with_main_scene() -> Node:
	var main: Node = load(MAIN_SCENE).instantiate()
	get_tree().root.add_child(main)
	return main


func test_scene_tree_reports_demo_nodes() -> void:
	var main := auto_free(_with_main_scene())
	var c := await _connect_client()
	await _auth(c)
	_send(c, {"cmd": "scene_tree", "id": 2, "root": "/root/Main", "depth": 6})
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", false)).is_true()
	var tree: Dictionary = reply["tree"]
	assert_str(tree["name"]).is_equal("Main")
	var label: Dictionary = tree["children"][0]
	assert_str(label["name"]).is_equal("StatusLabel")
	assert_str(label["text"]).is_equal("STATUS: IDLE")
	var origin: Dictionary = tree["children"][1]["children"][0]
	assert_str(origin["class"]).is_equal("XROrigin3D")
	assert_array(origin["groups"]).contains(["xr_origin"])


func test_get_and_set_property_roundtrip() -> void:
	var main := auto_free(_with_main_scene())
	var c := await _connect_client()
	await _auth(c)
	_send(
		c,
		{
			"cmd": "get_property",
			"id": 2,
			"path": "/root/Main/StatusLabel",
			"property": "text",
		}
	)
	var got := await _recv_dict(c)
	assert_str(got.get("value", "")).is_equal("STATUS: IDLE")
	_send(
		c,
		{
			"cmd": "set_property",
			"id": 3,
			"path": "/root/Main/StatusLabel",
			"property": "text",
			"value": "STATUS: RUNNING",
		}
	)
	var set_reply := await _recv_dict(c)
	assert_bool(set_reply.get("ok", false)).is_true()
	assert_str(main.get_node("StatusLabel").text).is_equal("STATUS: RUNNING")


func test_unknown_command_errors_and_connection_stays_up() -> void:
	var c := await _connect_client()
	await _auth(c)
	_send(c, {"cmd": "does_not_exist", "id": 9})
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("unknown or unavailable")
	# Connection stays up: a following ping is answered.
	_send(c, {"cmd": "ping", "id": 10})
	var pong := await _recv_dict(c)
	assert_bool(pong.get("ok", false)).is_true()
	assert_int(int(pong.get("id", -1))).is_equal(10)


func test_unregistered_command_errors_and_connection_stays_up() -> void:
	var c := await _connect_client()
	await _auth(c)
	_send(c, {"cmd": "capture", "id": 9})  # lands with W2-02-addon-capture
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", true)).is_false()
	_send(c, {"cmd": "ping", "id": 10})
	assert_bool((await _recv_dict(c)).get("ok", false)).is_true()


func test_restart_scene_without_current_scene_errors_loudly() -> void:
	var c := await _connect_client()
	await _auth(c)
	_send(c, {"cmd": "restart_scene", "id": 7})
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("no current scene")


func test_bad_node_path_is_an_error_reply_not_a_crash() -> void:
	var c := await _connect_client()
	await _auth(c)
	_send(
		c,
		{
			"cmd": "get_property",
			"id": 5,
			"path": "/root/No/Such/Node",
			"property": "text",
		}
	)
	var reply := await _recv_dict(c)
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("no node at")
