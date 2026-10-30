# gdUnit4 smoke suite for the demo harness (W2-01-qa-demo-project).
# Proves the scene contract that flows/smoke.yaml and the contract commands
# rely on: known label text, stable node names, settable property.
extends GdUnitTestSuite

const MAIN_SCENE := "res://scenes/main.tscn"
const BLACK_SCENE := "res://scenes/black.tscn"

func test_main_scene_loads_with_known_label_text() -> void:
	var packed: PackedScene = load(MAIN_SCENE)
	assert_object(packed).is_not_null()
	var scene: Node = auto_free(packed.instantiate())
	var label: Label = scene.get_node("StatusLabel")
	assert_str(label.text).is_equal("STATUS: IDLE")

func test_stable_node_names_present() -> void:
	var scene: Node = auto_free(load(MAIN_SCENE).instantiate())
	for path in ["StatusLabel", "World/XROrigin", "World/XROrigin/XRCamera3D",
			"World/XROrigin/ControllerLeft", "World/XROrigin/ControllerRight"]:
		assert_bool(scene.has_node(path)).is_true() \
			.append_failure_message("missing node: %s" % path)
	# XR classes match the operator fixture (demo_scene_tree.json) and give
	# W2-03 inject a real binding target.
	assert_str(scene.get_node("World/XROrigin").get_class()).is_equal("XROrigin3D")
	assert_str(scene.get_node("World/XROrigin/ControllerLeft").get_class()) \
		.is_equal("XRController3D")
	assert_str(scene.get_node("World/XROrigin/ControllerLeft").tracker) \
		.is_equal("left_hand")
	assert_str(scene.get_node("World/XROrigin/ControllerRight").tracker) \
		.is_equal("right_hand")

func test_property_is_settable() -> void:
	var scene: Node = auto_free(load(MAIN_SCENE).instantiate())
	var label: Label = scene.get_node("StatusLabel")
	label.text = "STATUS: RUNNING"
	assert_str(label.text).is_equal("STATUS: RUNNING")

func test_black_fixture_renders_black() -> void:
	var scene: Node = auto_free(load(BLACK_SCENE).instantiate())
	var rect: ColorRect = scene.get_node("BlackRect")
	assert_object(rect).is_not_null()
	assert_bool(rect.color.is_equal_approx(Color.BLACK)).is_true()
