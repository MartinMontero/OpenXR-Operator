## Authenticated loopback WebSocket command server — wire protocol v2.
##
## Contract: docs/contracts/wire-protocol.md (FROZEN — orchestrator-owned).
## Constants: addon/openxr_operator/protocol.gd (same freeze). This file may
## not change bind, port, limits, or auth semantics; those live in the
## contract. Card: W2-01-addon-server (F-001, F-017, F-027, S-02, S-16;
## audit TC-SEC-001, TC-SEC-002).
##
## S-16 auth nits, as specified — no more, no less:
##   - The first frame on every connection MUST be
##     {"cmd":"auth","token":"<64 hex>","protocol":2}. Exactly one attempt.
##   - 2-second deadline from connect; close 1008 on expiry or failure.
##   - Token compare is constant-time (_constant_time_equal).
##   - Nothing dispatches pre-auth, including error messages that would
##     confirm command names: pre-auth violations close with 1008 and no
##     reply body.
##   - Post-auth, an unknown or unregistered command gets an explicit error
##     reply and the connection stays up.
##
## S-02 token handling: 32 random bytes as 64 lowercase hex chars at
## user://openxr_operator.token, generated if absent. The token is never
## logged and never appears in any reply or artifact.
## P3-12 honesty: this file asks for 0o600 on the token file. That maps to a
## real syscall on Linux/macOS; on Windows there is no chmod 0600 equivalent
## through Godot and the call is a no-op — protection there is whatever the
## user-profile ACLs already provide. That is all this file claims.
##
## Test-only knobs: the five `var *_ms / max_*` limits below exist so the
## exit-gate tests can use shortened values (stated as such in the tests).
## They are settable only from code in this process — never from the wire,
## never from project settings — and default to the contract values.
extends Node

const Protocol = preload("res://addons/openxr_operator/protocol.gd")

const CLOSE_POLICY_VIOLATION := 1008
const CLOSE_TOO_BIG := 1009
const CLOSE_IDLE := 1001
const _RATE_WINDOW_MS := 1000
const _MAX_TREE_CHILDREN := 256
const _TOKEN_HEX_LEN := 64

var max_frame_bytes: int = Protocol.MAX_FRAME_BYTES
var max_peers: int = Protocol.MAX_PEERS
var max_msgs_per_sec: int = Protocol.MAX_MSGS_PER_SEC
var auth_deadline_ms: int = Protocol.AUTH_DEADLINE_MS
var idle_timeout_ms: int = Protocol.IDLE_TIMEOUT_MS

var _tcp := TCPServer.new()
var _peers: Array[_Peer] = []
var _token := ""
## Extra command handlers registered by sibling modules (capture, inject,
## editor bridge). cmd -> Callable(msg: Dictionary) -> Dictionary reply body.
var _handlers: Dictionary = {}
# Dispatch serialization (see _enqueue_dispatch): async handlers must not
# interleave replies.
var _queue: Array = []
var _draining := false


class _Peer:
	var ws: WebSocketPeer
	var authed := false
	var auth_attempted := false
	var connected_ms := 0
	var last_msg_ms := 0
	var msg_window_ms: Array[int] = []
	# Deferred close: a close requested mid-frame is executed on the next
	# poll so a just-sent reply (e.g. the F-027 protocol-mismatch message)
	# is flushed to the wire before the close frame.
	var pending_close: Array = []


func _ready() -> void:
	_ensure_token()
	var err := _tcp.listen(Protocol.PORT, Protocol.BIND)
	if err != OK:
		push_error(
			"openxr_operator: cannot bind %s:%d (err %d)" % [Protocol.BIND, Protocol.PORT, err]
		)
		return
	print("openxr_operator: command server listening on %s:%d" % [Protocol.BIND, Protocol.PORT])


func _exit_tree() -> void:
	for peer in _peers:
		if peer.ws.get_ready_state() != WebSocketPeer.STATE_CLOSED:
			peer.ws.close(1001, "server shutting down")
	_peers.clear()
	_tcp.stop()


## Registers a handler for a command implemented by a sibling module.
func register_command(cmd: String, handler: Callable) -> void:
	_handlers[cmd] = handler


## Test introspection: whether the listener is bound. No state beyond this
## is exposed; the token never leaves this object except by file.
func is_listening() -> bool:
	return _tcp.is_listening()


func _process(_delta: float) -> void:
	_accept_pending()
	var now := Time.get_ticks_msec()
	for peer in _peers.duplicate():
		_poll_peer(peer, now)


# -- connection lifecycle ---------------------------------------------------


func _accept_pending() -> void:
	while _tcp.is_connection_available():
		var stream := _tcp.take_connection()
		if _peers.size() >= max_peers:
			# No handshake, no reply: the peer is rejected outright.
			stream.disconnect_from_host()
			continue
		var ws := WebSocketPeer.new()
		# Inbound buffer holds twice the contract maximum so the size gate
		# (close 1009) is ours, not the library's.
		ws.inbound_buffer_size = max_frame_bytes * 2 + 1024
		var peer := _Peer.new()
		peer.ws = ws
		peer.connected_ms = Time.get_ticks_msec()
		peer.last_msg_ms = peer.connected_ms
		if ws.accept_stream(stream) != OK:
			stream.disconnect_from_host()
			continue
		_peers.append(peer)


func _poll_peer(peer: _Peer, now: int) -> void:
	peer.ws.poll()
	var state := peer.ws.get_ready_state()
	if state == WebSocketPeer.STATE_CLOSED:
		_peers.erase(peer)
		return
	# A close requested on an earlier frame executes now that any reply has
	# had a full poll cycle to flush. No further packets are processed.
	if not peer.pending_close.is_empty():
		if state == WebSocketPeer.STATE_OPEN:
			peer.ws.close(peer.pending_close[0], peer.pending_close[1])
		return
	if state != WebSocketPeer.STATE_OPEN:
		return
	while peer.ws.get_available_packet_count() > 0:
		var pkt := peer.ws.get_packet()
		_on_packet(peer, pkt, now)
		if not peer.pending_close.is_empty():
			break
	if not peer.authed and now - peer.connected_ms > auth_deadline_ms:
		_close(peer, CLOSE_POLICY_VIOLATION, "auth deadline")
	elif peer.authed and now - peer.last_msg_ms > idle_timeout_ms:
		_close(peer, CLOSE_IDLE, "idle timeout")


func _close(peer: _Peer, code: int, reason: String) -> void:
	# Defer to the next poll so any reply queued this frame flushes first
	# (see _Peer.pending_close). First close requested wins.
	if peer.pending_close.is_empty():
		peer.pending_close = [code, reason]


func _send(peer: _Peer, body: Dictionary) -> void:
	if peer.ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		peer.ws.send_text(JSON.stringify(body))


# -- limits and framing -------------------------------------------------------


func _on_packet(peer: _Peer, pkt: PackedByteArray, now: int) -> void:
	if pkt.size() > max_frame_bytes:
		_close(peer, CLOSE_TOO_BIG, "frame too large")
		return
	while not peer.msg_window_ms.is_empty() and now - peer.msg_window_ms[0] > _RATE_WINDOW_MS:
		peer.msg_window_ms.remove_at(0)
	if peer.msg_window_ms.size() >= max_msgs_per_sec:
		_close(peer, CLOSE_POLICY_VIOLATION, "rate limit")
		return
	peer.msg_window_ms.append(now)
	peer.last_msg_ms = now
	var parsed: Variant = JSON.parse_string(pkt.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("cmd"):
		if peer.authed and parsed is Dictionary and parsed.has("id"):
			_reply(peer, parsed, {"ok": false, "error": "malformed frame"})
		else:
			_close(peer, CLOSE_POLICY_VIOLATION, "malformed frame")
		return
	var msg: Dictionary = parsed
	if not peer.authed:
		_handle_pre_auth(peer, msg)
		return
	_enqueue_dispatch(peer, msg)


# -- auth (S-16: exactly this, no more, no less) -------------------------------


func _handle_pre_auth(peer: _Peer, msg: Dictionary) -> void:
	if peer.auth_attempted:
		_close(peer, CLOSE_POLICY_VIOLATION, "one auth attempt")
		return
	if msg.get("cmd") != "auth":
		# Nothing dispatches pre-auth — not even an error naming the command.
		_close(peer, CLOSE_POLICY_VIOLATION, "auth required")
		return
	peer.auth_attempted = true
	var proto: Variant = msg.get("protocol")
	if proto == null or int(proto) != Protocol.PROTOCOL_VERSION:
		# F-027: protocol mismatch closes with a clear message. The auth
		# command itself may be answered; no other command name is confirmed.
		_reply(
			peer,
			msg,
			{
				"ok": false,
				"protocol": Protocol.PROTOCOL_VERSION,
				"error": "protocol mismatch: server speaks protocol %d" % Protocol.PROTOCOL_VERSION,
			}
		)
		_close(peer, CLOSE_POLICY_VIOLATION, "protocol mismatch")
		return
	var token := str(msg.get("token", ""))
	if not _constant_time_equal(token, _token):
		_reply(peer, msg, {"ok": false, "error": "authentication failed"})
		_close(peer, CLOSE_POLICY_VIOLATION, "bad auth")
		return
	peer.authed = true
	_reply(peer, msg, {"ok": true, "protocol": Protocol.PROTOCOL_VERSION})


func _constant_time_equal(a: String, b: String) -> bool:
	# Fixed-work compare: every byte of both inputs is visited; the loop does
	# not exit early on a mismatch.
	var diff: int = abs(a.length() - b.length())
	var n: int = maxi(a.length(), b.length())
	for i in n:
		diff |= (
			(a.unicode_at(mini(i, a.length() - 1)) if a.length() > 0 else 0)
			^ (b.unicode_at(mini(i, b.length() - 1)) if b.length() > 0 else 0)
		)
	return diff == 0


# -- dispatch (post-auth only) -------------------------------------------------


func _enqueue_dispatch(peer: _Peer, msg: Dictionary) -> void:
	_queue.append([peer, msg])
	if not _draining:
		Callable(self, "_drain_queue").call()


func _drain_queue() -> void:
	_draining = true
	while not _queue.is_empty():
		var item: Array = _queue.pop_front()
		await _execute(item[0], item[1])
	_draining = false


func _execute(peer: _Peer, msg: Dictionary) -> void:
	if peer.ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return  # peer is gone; its close is handled by the poll loop
	var cmd := str(msg.get("cmd"))
	match cmd:
		"ping":
			_reply(peer, msg, {"ok": true})
		"scene_tree":
			_cmd_scene_tree(peer, msg)
		"get_property":
			_cmd_get_property(peer, msg)
		"set_property":
			_cmd_set_property(peer, msg)
		"restart_scene":
			_cmd_restart_scene(peer, msg)
		"auth":
			# One auth attempt per connection (S-16): a second attempt,
			# even post-auth, closes 1008.
			_close(peer, CLOSE_POLICY_VIOLATION, "one auth attempt")
		_:
			if _handlers.has(cmd):
				# Handlers may be coroutines (capture); plain Dictionaries
				# pass through await unchanged.
				@warning_ignore("redundant_await")
				var body: Variant = await _handlers[cmd].call(msg)
				if body is Dictionary:
					_reply(peer, msg, body)
				else:
					_reply(
						peer,
						msg,
						{
							"ok": false,
							"error": "handler for %s returned no reply" % cmd,
						}
					)
			else:
				_reply(
					peer,
					msg,
					{
						"ok": false,
						"error": "unknown or unavailable command: %s" % cmd,
					}
				)


func _reply(peer: _Peer, msg: Dictionary, body: Dictionary) -> void:
	# F-017: every request carries "id"; every reply echoes it. Godot's JSON
	# parser widens all numbers to float; re-narrow integral ids so the wire
	# carries "id":41, not "id":41.0.
	var id: Variant = msg.get("id")
	if id is float and id == floorf(id):
		id = int(id)
	body["id"] = id
	_send(peer, body)


func _cmd_scene_tree(peer: _Peer, msg: Dictionary) -> void:
	var root_path := str(msg.get("root", "/root"))
	var depth := int(msg.get("depth", 6))
	var node := get_node_or_null(NodePath(root_path))
	if node == null:
		_reply(peer, msg, {"ok": false, "error": "no node at %s" % root_path})
		return
	_reply(peer, msg, {"ok": true, "tree": _serialize_node(node, depth)})


func _serialize_node(node: Node, depth: int) -> Dictionary:
	var out := {
		"name": node.name,
		"class": node.get_class(),
		"path": str(node.get_path()),
		"visible": _node_visible(node),
		"groups": node.get_groups().map(func(g): return str(g)),
		"children": [],
		"children_truncated": 0,
	}
	if _has_property(node, "text"):
		out["text"] = node.get("text")
	if depth > 0:
		var children: Array = out["children"]
		var count := node.get_child_count()
		for i in mini(count, _MAX_TREE_CHILDREN):
			children.append(_serialize_node(node.get_child(i), depth - 1))
		out["children_truncated"] = maxi(0, count - _MAX_TREE_CHILDREN)
	return out


func _node_visible(node: Node) -> bool:
	if _has_property(node, "visible"):
		return bool(node.get("visible"))
	return true


func _has_property(node: Object, prop: String) -> bool:
	for info in node.get_property_list():
		if info.get("name") == prop:
			return true
	return false


func _cmd_get_property(peer: _Peer, msg: Dictionary) -> void:
	var node := get_node_or_null(NodePath(str(msg.get("path", ""))))
	if node == null:
		_reply(peer, msg, {"ok": false, "error": "no node at %s" % msg.get("path")})
		return
	var prop := str(msg.get("property", ""))
	if not _has_property(node, prop):
		_reply(
			peer,
			msg,
			{
				"ok": false,
				"error": "node %s has no property %s" % [node.get_path(), prop],
			}
		)
		return
	_reply(peer, msg, {"ok": true, "value": node.get(prop)})


func _cmd_set_property(peer: _Peer, msg: Dictionary) -> void:
	var node := get_node_or_null(NodePath(str(msg.get("path", ""))))
	if node == null:
		_reply(peer, msg, {"ok": false, "error": "no node at %s" % msg.get("path")})
		return
	var prop := str(msg.get("property", ""))
	if not _has_property(node, prop):
		_reply(
			peer,
			msg,
			{
				"ok": false,
				"error": "node %s has no property %s" % [node.get_path(), prop],
			}
		)
		return
	node.set(prop, msg.get("value"))
	_reply(peer, msg, {"ok": true})


func _cmd_restart_scene(peer: _Peer, msg: Dictionary) -> void:
	var tree := get_tree()
	if tree.current_scene == null:
		_reply(
			peer,
			msg,
			{
				"ok": false,
				"error": "no current scene to restart",
			}
		)
		return
	var err := tree.reload_current_scene()
	if err != OK:
		_reply(peer, msg, {"ok": false, "error": "reload failed (err %d)" % err})
		return
	_reply(peer, msg, {"ok": true})


# -- token (S-02) ---------------------------------------------------------------


func _ensure_token() -> void:
	if FileAccess.file_exists(Protocol.TOKEN_PATH):
		var f := FileAccess.open(Protocol.TOKEN_PATH, FileAccess.READ)
		if f != null:
			var existing := f.get_as_text().strip_edges()
			f.close()
			if existing.length() == _TOKEN_HEX_LEN:
				_token = existing
				return
		push_warning("openxr_operator: malformed token file; regenerating")
	var crypto := Crypto.new()
	_token = crypto.generate_random_bytes(32).hex_encode()
	var f := FileAccess.open(Protocol.TOKEN_PATH, FileAccess.WRITE)
	if f == null:
		push_error(
			"openxr_operator: cannot write token file (err %d)" % FileAccess.get_open_error()
		)
		return
	f.store_string(_token + "\n")
	f.close()
	# Best-effort 0600 (decimal 384; GDScript has no octal literal).
	# No-op on Windows; see the module docstring (P3-12).
	FileAccess.set_unix_permissions(ProjectSettings.globalize_path(Protocol.TOKEN_PATH), 384)
