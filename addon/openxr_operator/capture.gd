## T2/T3 capture with black-frame honesty.
##
## Card: W2-02-addon-capture (F-010, D-04 tier honesty; audit TC-SEC-005).
## Contract: docs/contracts/wire-protocol.md — frames go to disk; the channel
## carries {path, tier, sha256, ...}, never base64.
##
## F-010 disclosure (D-04 consequence, stated plainly): v1 capture is T2
## (mirror viewport readback when an XR interface is active) and T3 (desktop
## harness readback) ONLY. What T2/T3 prove: the pixels the main viewport
## composited on this machine. What they do NOT prove: the pixels the
## headset actually received. Exact composited-frame capture (F-010) is
## never resolved in v1 — that needs the API layer (W6, gated on D-04).
##
## Tier honesty (D-04): the reply carries the tier ACTUALLY used, derived
## from engine state (XRServer), never echoed from the request. A flow that
## declares t2 against a desktop harness gets "tier": "t3" back and the
## operator-side verifier rejects the mismatch; a report can never claim a
## fidelity the run did not have.
##
## Black frames (TC-SEC-005): an all-black or single-colour readback is
## REPORTED ("black": true, no path) and never written to disk as an image
## artifact. A silent black screenshot is the failure mode this exists to
## prevent.
extends Node

const _CAPTURE_DIR := "user://openxr_operator_captures"
const _LABEL_PATTERN := "^[A-Za-z0-9_-]+$"

# How long handle_capture waits for a presented frame before failing
# loudly. 5 s is right for a real game window; slow/remote test hosts can
# take >100 s to present the first frame (executed finding 2026-10-30),
# so tests raise this. Code-only knob, never settable from the wire.
var frame_timeout_ms := 5000

var _frame_id := 0
var _label_re := RegEx.new()


func _ready() -> void:
	_label_re.compile(_LABEL_PATTERN)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_CAPTURE_DIR))


## Wire this module into a server instance (register_command is server.gd's
## extension point; capture is async so it must go through the queue).
func register_on(server: Node) -> void:
	server.register_command("capture", handle_capture)


## The tier this engine process can actually produce right now.
func actual_tier() -> String:
	var xr := XRServer.primary_interface
	if xr != null and xr.is_initialized():
		return "t2"
	return "t3"


func handle_capture(msg: Dictionary) -> Dictionary:
	var label := str(msg.get("label", "frame"))
	if _label_re.search(label) == null:
		return {
			"ok": false,
			"error": "bad capture label %s (allowed: A-Z a-z 0-9 _ -)" % label,
		}
	var tier := actual_tier()
	# Never read back mid-frame (card): wait for the compositor. Bounded —
	# on a host where the window is not presenting (locked session,
	# minimized), frame_post_draw never fires; that is a loud named error,
	# never a hung command queue.
	if not await _await_frame_post_draw(frame_timeout_ms):
		return {
			"ok": false,
			"error":
			(
				(
					"capture unavailable: no presented frame within %d ms "
					+ "(display not rendering)"
				)
				% frame_timeout_ms
			),
		}
	var img := _readback()
	if img == null or img.is_empty() or _is_single_colour(img):
		# TC-SEC-005: reported, never an artifact. No path, no file.
		return {"ok": true, "frame": {"tier": tier, "black": true, "black_frame": true}}
	_frame_id += 1
	var rel_path := "%s/%s-%04d.png" % [_CAPTURE_DIR, label, _frame_id]
	var abs_path := ProjectSettings.globalize_path(rel_path)
	if img.save_png(rel_path) != OK:
		return {"ok": false, "error": "failed to write frame to %s" % rel_path}
	var bytes := FileAccess.get_file_as_bytes(rel_path)
	var sha := FileAccess.get_sha256(rel_path)
	return {
		"ok": true,
		"frame":
		{
			"path": abs_path,
			"tier": tier,
			"sha256": sha,
			"width": img.get_width(),
			"height": img.get_height(),
			"frame_id": _frame_id,
			"bytes": bytes.size(),
		},
	}


## Bounded wait for one presented frame. True when the compositor drew.
func _await_frame_post_draw(timeout_ms: int) -> bool:
	# NOTE: GDScript lambdas capture locals by value, so the flag rides in
	# a one-element array (reference type) — a plain bool never updates
	# (executed finding 2026-10-30).
	var fired := [false]
	var cb := func() -> void: fired[0] = true
	RenderingServer.frame_post_draw.connect(cb, CONNECT_ONE_SHOT)
	var start := Time.get_ticks_msec()
	while not fired[0] and Time.get_ticks_msec() - start < timeout_ms:
		await get_tree().process_frame
	if RenderingServer.frame_post_draw.is_connected(cb):
		RenderingServer.frame_post_draw.disconnect(cb)
	return fired[0]


func _readback() -> Image:
	var tree := get_tree()
	if tree == null or tree.root == null:
		return null
	var vp := tree.root.get_viewport()
	if vp == null or vp.get_texture() == null:
		return null
	return vp.get_texture().get_image()


## True when every pixel is identical (all-black is the common case, but any
## single-colour frame means the readback did not capture real content).
func _is_single_colour(img: Image) -> bool:
	img.convert(Image.FORMAT_RGBA8)
	var data := img.get_data()
	if data.size() < 4:
		return true
	var r := data[0]
	var g := data[1]
	var b := data[2]
	var a := data[3]
	var i := 4
	while i + 3 < data.size():
		if data[i] != r or data[i + 1] != g or data[i + 2] != b or data[i + 3] != a:
			return false
		i += 4
	return true
