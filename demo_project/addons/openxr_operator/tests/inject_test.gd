# W2-03-addon-inject: A3 injection floor tests (TC-SEC-006 binding assertion,
# bogus tracker rejection pre-injection, pose default, press synthesis).
# Headless-safe: no rendering involved. Log assertions use gdUnit4's
# assert_error().is_push_warning() against direct synchronous handler calls;
# wire tests go over the real loopback socket.
extends GdUnitTestSuite

const Server = preload("res://addons/openxr_operator/server.gd")
const Inject = preload("res://addons/openxr_operator/inject.gd")
const Protocol = preload("res://addons/openxr_operator/protocol.gd")
const MainScene = preload("res://scenes/main.tscn")

const URL := "ws://127.0.0.1:9099"

var _server: Node
var _inject: Node


func before() -> void:
	_server = Server.new()
	get_tree().root.add_child(_server)
	assert_bool(_server.is_listening()).is_true()
	_inject = Inject.new()
	get_tree().root.add_child(_inject)
	_inject.register_on(_server)


func after() -> void:
	_inject.free()
	_server.free()


func after_test() -> void:
	if InputMap.has_action("oxr_trigger"):
		InputMap.erase_action("oxr_trigger")
	for i in 5:
		await get_tree().process_frame


# -- wire helpers (same pattern as server_test.gd) -------------------------------


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


func _send(c: WebSocketPeer, msg: Dictionary) -> Dictionary:
	c.send_text(JSON.stringify(msg))
	c.poll()
	return await _recv_dict(c)


func _with_main_scene() -> Node:
	var main: Node = MainScene.instantiate()
	get_tree().root.add_child(main)
	return auto_free(main)


# -- TC-SEC-006: binding to nothing raises, never no-ops ---------------------------


func test_tc_sec_006_inject_without_binding_fails_on_wire_and_stays_up() -> void:
	# No scene added: no XRController3D exists for right_hand.
	var c := await _connect_authed()
	var reply := await _send(
		c,
		{
			"cmd": "inject",
			"id": 2,
			"op": "move_controller",
			"hand": "right",
			"position": [0.0, 1.0, -0.4],
			"rotation": [0.0, 0.0, 0.0, 1.0],
		}
	)
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("no XRController3D bound")
	assert_str(str(reply.get("tier", ""))).is_equal("a3")
	# Connection stays up.
	var pong := await _send(c, {"cmd": "ping", "id": 3})
	assert_bool(pong.get("ok", false)).is_true()


func test_bind_failure_is_logged() -> void:
	# Direct synchronous call: the log line is the F-012 audit trail.
	await (
		assert_error(
			func() -> void: _inject.handle_inject({"op": "move_controller", "hand": "left"})
		)
		. is_push_warning(
			(
				"openxr_operator inject: no XRController3D bound to tracker "
				+ "'left_hand' (F-012: silent no-op injection is a failure, never a pass)"
			)
		)
	)


# -- bogus trackers: rejected BEFORE injection --------------------------------------


func test_bogus_tracker_names_rejected_pre_injection() -> void:
	var main := _with_main_scene()
	var c := await _connect_authed()
	for bad in ["head", "left-hand", "", "LEFT_HAND"]:
		var reply := await _send(
			c,
			{
				"cmd": "inject",
				"id": 10,
				"op": "move_controller",
				"tracker": bad,
			}
		)
		assert_bool(reply.get("ok", true)).is_false().append_failure_message(
			"tracker '%s' was not rejected" % bad
		)
		assert_str(str(reply.get("error", ""))).contains("left_hand/right_hand")
	# Driver-shorthand hand field is validated the same way.
	var reply2 := await _send(
		c,
		{
			"cmd": "inject",
			"id": 11,
			"op": "move_controller",
			"hand": "head",
		}
	)
	assert_bool(reply2.get("ok", true)).is_false()
	# Pre-injection: nothing was touched.
	var left := main.get_node("World/XROrigin/ControllerLeft") as XRController3D
	assert_vector(left.transform.origin).is_equal(Vector3.ZERO)


func test_bogus_tracker_rejection_is_logged() -> void:
	await (
		assert_error(
			func() -> void: _inject.handle_inject({"op": "move_controller", "tracker": "head"})
		)
		. is_push_warning(
			(
				"openxr_operator inject: tracker rejected: must be one of "
				+ "left_hand/right_hand, got 'head'"
			)
		)
	)


# -- successful binding ----------------------------------------------------------------


func test_move_controller_binds_and_pose_lands() -> void:
	var main := _with_main_scene()
	var c := await _connect_authed()
	var reply := await _send(
		c,
		{
			"cmd": "inject",
			"id": 2,
			"op": "move_controller",
			"hand": "left",
			"position": [0.0, 1.0, -0.4],
			"rotation": [0.0, 0.0, 0.0, 1.0],
		}
	)
	assert_bool(reply.get("ok", false)).is_true()
	assert_str(str(reply.get("tier", ""))).is_equal("a3")
	assert_str(str(reply.get("node", ""))).is_equal("/root/Main/World/XROrigin/ControllerLeft")
	var left := main.get_node("World/XROrigin/ControllerLeft") as XRController3D
	assert_vector(left.transform.origin).is_equal_approx(
		Vector3(0.0, 1.0, -0.4), Vector3(0.0001, 0.0001, 0.0001)
	)


func test_pose_default_applied_when_omitted() -> void:
	var main := _with_main_scene()
	var right := main.get_node("World/XROrigin/ControllerRight") as XRController3D
	right.transform = Transform3D(Basis(), Vector3(9.0, 9.0, 9.0))
	var c := await _connect_authed()
	var reply := await _send(
		c,
		{
			"cmd": "inject",
			"id": 2,
			"op": "move_controller",
			"hand": "right",
		}
	)
	assert_bool(reply.get("ok", false)).is_true()
	assert_vector(right.transform.origin).is_equal(Vector3.ZERO)


# -- press (A3 Input synthesis) -----------------------------------------------------------


func test_press_synthesizes_input_action() -> void:
	var main := _with_main_scene()
	var c := await _connect_authed()
	var reply := await _send(
		c,
		{
			"cmd": "inject",
			"id": 2,
			"op": "press",
			"hand": "right",
			"action_name": "oxr_trigger",
			"float_value": 1.0,
		}
	)
	assert_bool(reply.get("ok", false)).is_true()
	assert_bool(Input.is_action_pressed("oxr_trigger")).is_true()
	var reply2 := await _send(
		c,
		{
			"cmd": "inject",
			"id": 3,
			"op": "press",
			"hand": "right",
			"action_name": "oxr_trigger",
			"float_value": 0.0,
		}
	)
	assert_bool(reply2.get("ok", false)).is_true()
	assert_bool(Input.is_action_pressed("oxr_trigger")).is_false()


func test_press_without_binding_fails() -> void:
	# No scene: no XRController3D, press must fail, not no-op.
	var c := await _connect_authed()
	var reply := await _send(
		c,
		{
			"cmd": "inject",
			"id": 2,
			"op": "press",
			"hand": "left",
			"action_name": "oxr_trigger",
			"float_value": 1.0,
		}
	)
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("no XRController3D bound")


func test_unknown_inject_op_is_named_error() -> void:
	var c := await _connect_authed()
	var reply := await _send(
		c,
		{
			"cmd": "inject",
			"id": 2,
			"op": "teleport",
			"hand": "left",
		}
	)
	assert_bool(reply.get("ok", true)).is_false()
	assert_str(str(reply.get("error", ""))).contains("unknown inject op")
