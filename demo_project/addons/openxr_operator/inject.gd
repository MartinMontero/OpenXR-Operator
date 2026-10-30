## A3 injection floor — desktop harness input synthesis, no OpenXR runtime
## involvement (D-04). Card: W2-03-addon-inject (F-012, S-03; audit TC-SEC-006).
##
## F-012: a silent no-op injection is the worst outcome. Every injection
## request either measurably binds (an XRController3D with the requested
## tracker exists and the post-injection assertion passes) or fails loudly —
## named error on the wire AND a log line. Never a silent return.
##
## Tracker constraint: only "left_hand" / "right_hand" (or driver-side
## shorthand hand "left" / "right") are accepted. Anything else is rejected
## BEFORE any injection attempt, with an error naming the constraint.
##
## A3 semantics (what this tier proves): move_controller drives the bound
## XRController3D's local transform directly; press synthesizes Input action
## state (Input.action_press/release) so desktop-harness game code reading
## Input sees it. Neither involves an XR runtime; no claim is made about
## headset-tracked state.
##
## S-03: this file introduces NO class_name. Sibling modules are referenced
## by preload path only, so there is no class-name table to drift out of
## sync; the grep proving that is pasted in the card evidence.
extends Node

const _ALLOWED_TRACKERS: Array[String] = ["left_hand", "right_hand"]
const _HAND_TO_TRACKER := {"left": "left_hand", "right": "right_hand"}
const _DEFAULT_POSITION := Vector3.ZERO
const _DEFAULT_ROTATION := Quaternion.IDENTITY


func register_on(server: Node) -> void:
	server.register_command("inject", handle_inject)


func handle_inject(msg: Dictionary) -> Dictionary:
	var tracker := _resolve_tracker(msg)
	if tracker.is_empty():
		var given := str(msg.get("tracker", msg.get("hand", "")))
		var err := (
			"tracker rejected: must be one of %s, got '%s'" % ["/".join(_ALLOWED_TRACKERS), given]
		)
		push_warning("openxr_operator inject: " + err)
		return {"ok": false, "tier": "a3", "error": err}
	var op := str(msg.get("op", ""))
	match op:
		"move_controller":
			return _move_controller(msg, tracker)
		"press":
			return _press(msg, tracker)
		_:
			var err := "unknown inject op '%s' (expected move_controller|press)" % op
			push_warning("openxr_operator inject: " + err)
			return {"ok": false, "tier": "a3", "error": err}


## Empty string when the request's tracker/hand is not on the allowlist.
func _resolve_tracker(msg: Dictionary) -> String:
	if msg.has("tracker"):
		var t := str(msg.get("tracker"))
		return t if _ALLOWED_TRACKERS.has(t) else ""
	var hand := str(msg.get("hand", ""))
	return _HAND_TO_TRACKER.get(hand, "")


## The XRController3D bound to the tracker, or null. Null is a failure
## everywhere it matters — callers never no-op past it (F-012).
func _find_controller(tracker: StringName) -> XRController3D:
	for node in get_tree().root.find_children("*", "XRController3D", true, false):
		var controller := node as XRController3D
		if controller != null and controller.tracker == tracker:
			return controller
	return null


func _move_controller(msg: Dictionary, tracker: String) -> Dictionary:
	var controller := _find_controller(tracker)
	if controller == null:
		return _bind_failure(tracker)
	var position := _to_vector3(msg.get("position"), _DEFAULT_POSITION)
	var rotation := _to_quaternion(msg.get("rotation"), _DEFAULT_ROTATION)
	controller.transform = Transform3D(Basis(rotation), position)
	# Post-injection binding assertion: the pose must have landed on the
	# bound node. If it did not, the injection silently bound nothing.
	var actual := controller.transform
	if (
		not actual.origin.is_equal_approx(position)
		or not actual.basis.get_rotation_quaternion().is_equal_approx(rotation)
	):
		var err := "binding assertion failed: pose did not land on %s" % controller.get_path()
		push_warning("openxr_operator inject: " + err)
		return {"ok": false, "tier": "a3", "error": err}
	return {
		"ok": true,
		"tier": "a3",
		"tracker": tracker,
		"node": str(controller.get_path()),
	}


func _press(msg: Dictionary, tracker: String) -> Dictionary:
	var controller := _find_controller(tracker)
	if controller == null:
		return _bind_failure(tracker)
	var action := str(msg.get("action_name", ""))
	if action.is_empty():
		var err := "press rejected: empty action_name"
		push_warning("openxr_operator inject: " + err)
		return {"ok": false, "tier": "a3", "error": err}
	var value := float(msg.get("float_value", 1.0))
	# A3 desktop synthesis: drive the Input singleton. Register the action if
	# the harness project does not declare it, so action_press has an effect.
	if not InputMap.has_action(action):
		InputMap.add_action(action)
	if value > 0.0:
		Input.action_press(action, value)
	else:
		Input.action_release(action)
	# Post-injection assertion: the Input state must reflect the press.
	var pressed := Input.is_action_pressed(action)
	if value > 0.0 and not pressed:
		var err := "binding assertion failed: Input action '%s' not pressed" % action
		push_warning("openxr_operator inject: " + err)
		return {"ok": false, "tier": "a3", "error": err}
	if value <= 0.0 and pressed:
		var err := "binding assertion failed: Input action '%s' still pressed" % action
		push_warning("openxr_operator inject: " + err)
		return {"ok": false, "tier": "a3", "error": err}
	return {"ok": true, "tier": "a3", "tracker": tracker, "action": action}


func _bind_failure(tracker: String) -> Dictionary:
	var err := (
		(
			"no XRController3D bound to tracker '%s' "
			+ "(F-012: silent no-op injection is a failure, never a pass)"
		)
		% tracker
	)
	push_warning("openxr_operator inject: " + err)
	return {"ok": false, "tier": "a3", "error": err}


func _to_vector3(value: Variant, default: Vector3) -> Vector3:
	if value is Array and value.size() == 3:
		return Vector3(float(value[0]), float(value[1]), float(value[2]))
	if value is Vector3:
		return value
	return default


func _to_quaternion(value: Variant, default: Quaternion) -> Quaternion:
	if value is Array and value.size() == 4:
		return Quaternion(float(value[0]), float(value[1]), float(value[2]), float(value[3]))
	if value is Quaternion:
		return value
	return default
