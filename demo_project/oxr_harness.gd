## Demo harness wiring: assembles the addon modules (server, capture,
## inject, editor bridge) in a running game. QA-owned demo code; the addon's
## production autoload/editor plugin (plugin.gd) is a known escalated gap.
##
## Activation: starts only when (a) launched with --oxr-harness, or
## (b) EngineDebugger.is_active() (editor-run / debug session). Inert
## otherwise, so plain scene loads and headless tests are unaffected.
extends Node

const Server = preload("res://addons/openxr_operator/server.gd")
const Capture = preload("res://addons/openxr_operator/capture.gd")
const Inject = preload("res://addons/openxr_operator/inject.gd")
const EditorBridge = preload("res://addons/openxr_operator/editor_bridge.gd")

var _server: Node


func _ready() -> void:
	var wanted := EngineDebugger.is_active() \
		or OS.get_cmdline_args().has("--oxr-harness")
	if not wanted:
		return
	_server = Server.new()
	get_tree().root.add_child.call_deferred(_server)
	_wire.call_deferred()


func _wire() -> void:
	if _server == null or not _server.is_listening():
		print("oxr_harness: server not listening (port busy?); harness inert")
		return
	var capture: Node = Capture.new()
	get_tree().root.add_child(capture)
	capture.register_on(_server)
	var inject: Node = Inject.new()
	get_tree().root.add_child(inject)
	inject.register_on(_server)
	var bridge: Node = EditorBridge.new()
	get_tree().root.add_child(bridge)
	bridge.register_on(_server)
	bridge.ack_timeout_ms = 30000  # editor scan can be slow on first run
	print("oxr_harness: server+capture+inject+editor_bridge wired")
