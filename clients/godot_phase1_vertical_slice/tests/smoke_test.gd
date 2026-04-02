## Smoke harness for the Phase-1 vertical slice Godot client.
##
## Exercises the real production wiring:
##   Bootstrap -> TitleScreen (via BootstrapController._ready)
##   mode_selected signal -> session creation -> MainGame added by BootstrapController
##   SessionStore.snapshot_updated signal -> HUD label update
##   SessionStore background polling -> post-mount authoritative snapshot refresh
##
## Both supported modes are validated by bootstrap discovery, and one supported
## mode is exercised per run via MODSIM_GODOT_SMOKE_MODE:
##   - phase1_process_sandbox_v1  (default)
##   - heater_flash_guided_build_v1  (set MODSIM_GODOT_SMOKE_MODE to run it)

extends SceneTree

const BOOTSTRAP_SCENE := preload("res://scenes/Bootstrap.tscn")
const DEFAULT_SMOKE_MODE := "phase1_process_sandbox_v1"
const KEEP_OUT_HALF_WIDTH := 0.8
const KEEP_OUT_HALF_HEIGHT := 0.65


func _init() -> void:
	call_deferred("_run")


func _assert(condition: bool, message: String) -> void:
	if not condition:
		push_error("SMOKE ASSERTION FAILED: %s" % message)
		quit(1)


func _add_bootstrap_to_root() -> Node:
	var bootstrap_root := BOOTSTRAP_SCENE.instantiate()
	_assert(bootstrap_root != null, "Bootstrap scene should instantiate")
	root.add_child(bootstrap_root)
	return bootstrap_root


func _get_store(bootstrap_root: Node) -> Node:
	var store: Node = bootstrap_root.get_node_or_null("SessionStore")
	_assert(store != null, "SessionStore child must exist on Bootstrap")
	return store


func _get_backend(bootstrap_root: Node) -> Node:
	var backend: Node = bootstrap_root.get_node_or_null("BackendClient")
	_assert(backend != null, "BackendClient child must exist on Bootstrap")
	return backend


func _wait_for_bootstrap_loaded(store: Node) -> void:
	if store.bootstrap_data.is_empty():
		await store.bootstrap_updated


func _wait_for_title_screen(bootstrap_root: Node, max_frames: int = 10) -> Node:
	for _frame in range(max_frames):
		var title: Node = _find_active_title_screen(bootstrap_root)
		if title != null:
			return title
		await process_frame
	return null


func _find_active_title_screen(bootstrap_root: Node) -> Node:
	var screen_root: Node = bootstrap_root.get_node_or_null("ScreenRoot")
	_assert(screen_root != null, "ScreenRoot Control must exist on Bootstrap")
	for child in screen_root.get_children():
		if child.has_signal("mode_selected") and child.has_method("_on_sandbox_pressed"):
			return child
	return null


func _wait_for_snapshot(store: Node) -> Dictionary:
	await store.snapshot_updated
	return store.latest_snapshot


func _wait_for_poll_update(store: Node, previous_poll_count: int, max_frames: int = 240) -> void:
	for _frame in range(max_frames):
		if int(store.poll_success_count) > previous_poll_count and String(store.last_snapshot_update_source) == "poll":
			return
		await process_frame
	_assert(false, "Expected a post-mount polling-only snapshot update")


func _wait_for_backend_request_in_flight(backend: Node, max_frames: int = 240) -> void:
	for _frame in range(max_frames):
		if bool(backend.is_request_in_flight()):
			return
		await process_frame
	_assert(false, "Expected BackendClient to have an in-flight request")


func _selected_mode_id() -> String:
	var requested: String = OS.get_environment("MODSIM_GODOT_SMOKE_MODE").strip_edges()
	if requested == "":
		return DEFAULT_SMOKE_MODE
	return requested


func _find_main_game(bootstrap_root: Node) -> Node:
	var screen_root: Node = bootstrap_root.get_node_or_null("ScreenRoot")
	if screen_root == null:
		return null
	for child in screen_root.get_children():
		if not (child.has_signal("mode_selected") and child.has_method("_on_sandbox_pressed")):
			return child
	return null


func _wait_for_main_game(bootstrap_root: Node, max_frames: int = 10) -> Node:
	for _frame in range(max_frames):
		var main: Node = _find_main_game(bootstrap_root)
		if main != null:
			return main
		await process_frame
	return null


func _wait_for_status_contains(status_label: Label, expected_substring: String, max_frames: int = 120) -> void:
	for _frame in range(max_frames):
		if status_label.text.contains(expected_substring):
			return
		await process_frame
	_assert(false, "Expected status label to contain '%s', got '%s'" % [expected_substring, status_label.text])


func _wait_for_status_contains_any(status_label: Label, expected_substrings: PackedStringArray, max_frames: int = 120) -> void:
	for _frame in range(max_frames):
		for expected in expected_substrings:
			if status_label.text.contains(expected):
				return
		await process_frame
	_assert(false, "Expected status label to contain one of %s, got '%s'" % [", ".join(expected_substrings), status_label.text])


func _wait_for_goal_or_inventory(store: Node, max_frames: int = 240) -> void:
	for _frame in range(max_frames):
		var feed: Dictionary = store.latest_snapshot.get("simulation_snapshot", {}).get("feed_inventory_by_material_id", {})
		var total_feed: float = 0.0
		for value in feed.values():
			total_feed += float(value)
		if total_feed > 0.0:
			return
		var products: Dictionary = store.product_inventory()
		var total_product: float = 0.0
		for value in products.values():
			total_product += float(value)
		if total_product > 0.0:
			return
		await process_frame
	_assert(false, "Expected feed or product inventory after sandbox UI command sequence")


func _press_selected_title_button(title_screen: Node, selected_mode: String) -> void:
	var button_path: String = "Center/VBox/SandboxButton"
	if selected_mode == "heater_flash_guided_build_v1":
		button_path = "Center/VBox/TutorialButton"
	var button: Button = title_screen.get_node_or_null(button_path) as Button
	_assert(button != null, "Expected title button at %s" % button_path)
	button.pressed.emit()


func _select_build_item(build_panel: Node, desired_item_id: String, max_steps: int = 20) -> void:
	var build_item_label: Label = build_panel.get_node_or_null("BuildItemLabel") as Label
	var build_item_next_button: Button = build_panel.get_node_or_null("BuildItemNextButton") as Button
	_assert(build_item_label != null, "BuildItemLabel must exist")
	_assert(build_item_next_button != null, "BuildItemNextButton must exist")
	for _step in range(max_steps):
		if build_item_label.text == "Selected build item: %s" % desired_item_id:
			return
		build_item_next_button.pressed.emit()
		await process_frame
	_assert(false, "Expected build item selection for %s, got '%s'" % [desired_item_id, build_item_label.text])


func _select_line_endpoint(label: Label, next_button: Button, label_prefix: String, desired_endpoint_id: String, max_steps: int = 40) -> void:
	for _step in range(max_steps):
		if label.text == "%s%s" % [label_prefix, desired_endpoint_id]:
			return
		next_button.pressed.emit()
		await process_frame
	_assert(false, "Expected endpoint selection %s%s, got '%s'" % [label_prefix, desired_endpoint_id, label.text])


func _latest_line_entity(snapshot: Dictionary, source_id: String, target_id: String) -> Dictionary:
	var board_layout: Dictionary = snapshot.get("board_layout", {})
	var line_entities: Dictionary = board_layout.get("line_entities_by_line_id", {})
	for line_id in line_entities.keys():
		var entity: Variant = line_entities[line_id]
		if entity is Dictionary \
		and String(entity.get("source", "")) == source_id \
		and String(entity.get("target", "")) == target_id:
			return entity
	return {}


func _sorted_keys(value: Dictionary) -> PackedStringArray:
	var keys := PackedStringArray()
	for key in value.keys():
		keys.append(String(key))
	keys.sort()
	return keys


func _expected_boundary_ids(snapshot: Dictionary) -> PackedStringArray:
	var ids := PackedStringArray()
	var topology_envelope: Dictionary = snapshot.get("topology", {})
	var topology: Dictionary = topology_envelope.get("topology", {})
	var nodes: Array = topology.get("nodes", [])
	for node_value in nodes:
		if not (node_value is Dictionary):
			continue
		var node: Dictionary = node_value
		if String(node.get("node_kind", "")) == "boundary":
			ids.append(String(node.get("node_id", "")))
	ids.sort()
	return ids


func _assert_path_is_orthogonal(path_xy: Array, message_prefix: String) -> void:
	_assert(path_xy.size() >= 2, "%s must contain at least two points" % message_prefix)
	for index in range(path_xy.size() - 1):
		var start_point: Variant = path_xy[index]
		var end_point: Variant = path_xy[index + 1]
		_assert(start_point is Array and end_point is Array, "%s points must be arrays" % message_prefix)
		var start_point_array: Array = start_point
		var end_point_array: Array = end_point
		_assert(start_point_array.size() == 2 and end_point_array.size() == 2,
			"%s points must be [x, y] pairs" % message_prefix)
		var start_x := float(start_point_array[0])
		var start_y := float(start_point_array[1])
		var end_x := float(end_point_array[0])
		var end_y := float(end_point_array[1])
		_assert(is_equal_approx(start_x, end_x) or is_equal_approx(start_y, end_y),
			"%s must use only orthogonal segments" % message_prefix)


func _assert_path_avoids_keepout(path_xy: Array, center: Vector2, message_prefix: String) -> void:
	var min_x := center.x - KEEP_OUT_HALF_WIDTH
	var max_x := center.x + KEEP_OUT_HALF_WIDTH
	var min_y := center.y - KEEP_OUT_HALF_HEIGHT
	var max_y := center.y + KEEP_OUT_HALF_HEIGHT
	for index in range(path_xy.size() - 1):
		var start_point := path_xy[index] as Array
		var end_point := path_xy[index + 1] as Array
		var start_x := float(start_point[0])
		var start_y := float(start_point[1])
		var end_x := float(end_point[0])
		var end_y := float(end_point[1])
		if is_equal_approx(start_y, end_y):
			if start_y <= min_y or start_y >= max_y:
				continue
			var segment_min_x := minf(start_x, end_x)
			var segment_max_x := maxf(start_x, end_x)
			_assert(segment_max_x <= min_x or segment_min_x >= max_x,
				"%s horizontal segment must avoid obstacle keep-out" % message_prefix)
		else:
			if start_x <= min_x or start_x >= max_x:
				continue
			var segment_min_y := minf(start_y, end_y)
			var segment_max_y := maxf(start_y, end_y)
			_assert(segment_max_y <= min_y or segment_min_y >= max_y,
				"%s vertical segment must avoid obstacle keep-out" % message_prefix)


func _run() -> void:
	var bootstrap_root: Node = _add_bootstrap_to_root()

	var backend: Node = _get_backend(bootstrap_root)
	_assert(backend != null, "BackendClient node must be present before bootstrap loads")

	var store: Node = _get_store(bootstrap_root)
	_assert(store != null, "SessionStore node must be present before bootstrap loads")

	await _wait_for_bootstrap_loaded(store)

	var modes: Array = store.supported_mode_ids()
	_assert(modes.has("phase1_process_sandbox_v1"),
		"phase1_process_sandbox_v1 must be listed in bootstrap supported_mode_ids")
	_assert(modes.has("heater_flash_guided_build_v1"),
		"heater_flash_guided_build_v1 must be listed in bootstrap supported_mode_ids")

	var title_screen: Node = await _wait_for_title_screen(bootstrap_root)
	_assert(title_screen != null,
		"TitleScreen must be the active screen inside ScreenRoot after bootstrap")

	var selected_mode: String = _selected_mode_id()
	_assert(
		selected_mode == "phase1_process_sandbox_v1"
			or selected_mode == "heater_flash_guided_build_v1",
		"MODSIM_GODOT_SMOKE_MODE must be phase1_process_sandbox_v1 or heater_flash_guided_build_v1"
	)

	_press_selected_title_button(title_screen, selected_mode)
	await _wait_for_snapshot(store)

	_assert(store.active_session_id != "",
		"Session ID must be set on SessionStore after selected mode start")
	_assert(store.active_mode_id == selected_mode,
		"active_mode_id must match the selected mode after start")
	_assert(store.latest_snapshot.has("simulation_snapshot"),
		"latest_snapshot must contain simulation_snapshot key after session creation")

	var main_game: Node = await _wait_for_main_game(bootstrap_root)
	_assert(main_game != null,
		"MainGame must be added to ScreenRoot by BootstrapController after mode start")

	var fixed_camera: Camera3D = main_game.get_node_or_null("World/FixedCamera") as Camera3D
	_assert(fixed_camera != null, "Fixed camera must exist at World/FixedCamera")
	_assert(fixed_camera.current, "Fixed camera must be marked current")

	var pause_button: Node = main_game.find_child("PauseButton", true, false)
	_assert(pause_button == null, "Pause button must be omitted from MainGame")
	_assert(not InputMap.has_action("pause"), "Pause hotkey action must not exist")

	var hud: Node = main_game.get_node_or_null("CanvasLayer/HUD")
	_assert(hud != null, "HudController must exist at CanvasLayer/HUD in MainGame")
	var world_renderer: Node = main_game.get_node_or_null("World/WorldRenderer")
	_assert(world_renderer != null, "WorldRenderer must exist at World/WorldRenderer in MainGame")

	var snapshot_update_count_before_mount: int = int(store.snapshot_update_count)
	var poll_count_before_mount: int = int(store.poll_success_count)
	_assert(store.is_polling_active, "Background polling must start after session creation")
	await _wait_for_poll_update(store, poll_count_before_mount)
	await process_frame
	_assert(int(store.snapshot_update_count) > snapshot_update_count_before_mount,
		"Polling must deliver at least one post-mount snapshot update")

	_assert(hud.cash_label.text.begins_with("Cash:"),
		"HUD cash label must start with 'Cash:' after snapshot_updated signal")
	_assert(not hud.cash_label.text.ends_with("--"),
		"HUD cash label must not be the default '--' after snapshot_updated signal")
	_assert(hud.mode_label.text.contains(selected_mode),
		"HUD mode label must reflect the selected mode_id after snapshot_updated signal")
	_assert(hud.stage_label.text.begins_with("Stage:"),
		"HUD stage label must render progression stage state")
	_assert(hud.research_label.text.begins_with("Research:"),
		"HUD research label must render available research state")
	_assert(hud.unlocked_items_label.text.begins_with("Unlocked Build Items:"),
		"HUD unlocked items label must render progression item state")
	_assert(world_renderer.has_method("rendered_boundary_ids"),
		"WorldRenderer must expose rendered boundary ids for smoke inspection")
	var rendered_boundary_ids: PackedStringArray = world_renderer.rendered_boundary_ids()
	_assert(rendered_boundary_ids == _expected_boundary_ids(store.latest_snapshot),
		"WorldRenderer boundary ids must match authoritative topology presence")

	var build_panel: Node = main_game.get_node_or_null("CanvasLayer/HUD/BuildPanel")
	_assert(build_panel != null, "BuildCommandPanel must exist at CanvasLayer/HUD/BuildPanel")

	var build_selected_button: Button = build_panel.get_node_or_null("BuildSelectedButton") as Button
	var line_source_label: Label = build_panel.get_node_or_null("LineSourceLabel") as Label
	var line_source_next_button: Button = build_panel.get_node_or_null("LineSourceNextButton") as Button
	var line_target_label: Label = build_panel.get_node_or_null("LineTargetLabel") as Label
	var line_target_next_button: Button = build_panel.get_node_or_null("LineTargetNextButton") as Button
	var submit_research_button: Button = build_panel.get_node_or_null("SubmitResearchButton") as Button
	var buy_feed_button: Button = build_panel.get_node_or_null("BuyFeedButton") as Button
	var sell_product_button: Button = build_panel.get_node_or_null("SellProductButton") as Button
	var restart_button: Button = build_panel.get_node_or_null("RestartButton") as Button
	var build_item_label: Label = build_panel.get_node_or_null("BuildItemLabel") as Label
	var research_status_label: Label = build_panel.get_node_or_null("ResearchStatusLabel") as Label
	var status_label: Label = build_panel.get_node_or_null("StatusLabel") as Label

	_assert(build_selected_button != null, "BuildSelectedButton must exist")
	_assert(line_source_label != null, "LineSourceLabel must exist")
	_assert(line_source_next_button != null, "LineSourceNextButton must exist")
	_assert(line_target_label != null, "LineTargetLabel must exist")
	_assert(line_target_next_button != null, "LineTargetNextButton must exist")
	_assert(submit_research_button != null, "SubmitResearchButton must exist")
	_assert(buy_feed_button != null, "BuyFeedButton must exist")
	_assert(sell_product_button != null, "SellProductButton must exist")
	_assert(restart_button != null, "RestartButton must exist")
	_assert(build_item_label != null, "BuildItemLabel must exist")
	_assert(research_status_label != null, "ResearchStatusLabel must exist")
	_assert(status_label != null, "StatusLabel must exist")

	_assert(build_item_label.text.begins_with("Selected build item:"),
		"Build item label must show currently selected unlocked item")

	if selected_mode == "phase1_process_sandbox_v1":
		await _select_build_item(build_panel, "place_inlet_gas_separator")
		build_selected_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Built place_inlet_gas_separator")

		build_selected_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Built place_inlet_gas_separator")

		await _select_build_item(build_panel, "build_process_line")
		await _select_line_endpoint(line_source_label, line_source_next_button, "Line source: ", "sweet_wet_gas")
		await _select_line_endpoint(line_target_label, line_target_next_button, "Line target: ", "separator_1.inlet")
		build_selected_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Built build_process_line")
		_assert(not status_label.text.contains("Line build requires explicit endpoints"),
			"Explicit line endpoint authoring must replace the old fixed rejection")
		var feed_line_entity := _latest_line_entity(store.latest_snapshot, "sweet_wet_gas", "separator_1.inlet")
		_assert(not feed_line_entity.is_empty(),
			"Sandbox snapshot must store the sweet_wet_gas -> separator_1.inlet line")
		_assert_path_is_orthogonal(feed_line_entity.get("path_xy", []),
			"Feed line path")
		var rendered_unit_ids: PackedStringArray = world_renderer.rendered_unit_ids()
		var expected_unit_ids: PackedStringArray = _sorted_keys(
			store.latest_snapshot.get("board_layout", {}).get("unit_entities_by_process_id", {})
		)
		_assert(rendered_unit_ids == expected_unit_ids,
			"WorldRenderer unit ids must match authoritative unit ids after sandbox builds")
		var rendered_line_ids: PackedStringArray = world_renderer.rendered_line_ids()
		var expected_line_ids: PackedStringArray = _sorted_keys(
			store.latest_snapshot.get("board_layout", {}).get("line_entities_by_line_id", {})
		)
		_assert(rendered_line_ids == expected_line_ids,
			"WorldRenderer line ids must match authoritative line ids after first line build")

		await _select_line_endpoint(line_source_label, line_source_next_button, "Line source: ", "separator_1.vapor_outlet")
		await _select_line_endpoint(line_target_label, line_target_next_button, "Line target: ", "separator_gas")
		var request_started_before_line: int = int(backend.request_started_count)
		var request_wait_before_line: int = int(backend.request_wait_count)
		await _wait_for_backend_request_in_flight(backend)
		build_selected_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Built build_process_line")
		_assert(int(backend.request_started_count) > request_started_before_line,
			"Line build should issue a real HTTP request through BackendClient")
		_assert(int(backend.request_wait_count) > request_wait_before_line,
			"Line build should wait behind an in-flight background poll request at least once")
		_assert(int(backend.request_timeout_count) == 0,
			"Serialized request sequencing should not require transport timeouts")
		var vapor_line_entity := _latest_line_entity(store.latest_snapshot, "separator_1.vapor_outlet", "separator_gas")
		_assert(not vapor_line_entity.is_empty(),
			"Sandbox snapshot must store the separator_1.vapor_outlet -> separator_gas line")
		var vapor_path_xy: Array = vapor_line_entity.get("path_xy", [])
		_assert_path_is_orthogonal(vapor_path_xy, "Vapor outlet line path")
		_assert(vapor_path_xy.size() >= 3,
			"Vapor outlet line should use an elbowed path when separator_2 occupies the direct route")
		_assert_path_avoids_keepout(vapor_path_xy, Vector2(4.0, 0.0),
			"Vapor outlet line path")
		rendered_line_ids = world_renderer.rendered_line_ids()
		expected_line_ids = _sorted_keys(
			store.latest_snapshot.get("board_layout", {}).get("line_entities_by_line_id", {})
		)
		_assert(rendered_line_ids == expected_line_ids,
			"WorldRenderer line ids must match authoritative line ids after vapor line build")

		buy_feed_button.pressed.emit()
		await _wait_for_status_contains_any(status_label, PackedStringArray(["Bought", "Buy feed failed"]))
	else:
		buy_feed_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Feed purchase unavailable in tutorial")
		_assert(world_renderer.rendered_boundary_ids() == _expected_boundary_ids(store.latest_snapshot),
			"Tutorial mode must render authoritative boundary ids")

	submit_research_button.pressed.emit()
	await _wait_for_status_contains_any(status_label, PackedStringArray(["Research submitted", "Research failed", "No research available"]))
	_assert(research_status_label.text.begins_with("Research target:"),
		"Build panel research status label must expose available research id")

	sell_product_button.pressed.emit()
	await _wait_for_status_contains_any(status_label, PackedStringArray(["Sold", "Sell product failed"]))

	if selected_mode == "heater_flash_guided_build_v1":
		_assert(hud.goals_label.text.begins_with("Tutorial Goals:"),
			"HUD goals label must remain wired for tutorial mode")
	else:
		await _wait_for_goal_or_inventory(store)

	var original_session_id: String = store.active_session_id
	restart_button.pressed.emit()
	await _wait_for_status_contains(status_label, "Session restarted")
	_assert(store.active_session_id == original_session_id,
		"Restart via UI must preserve active session id")
	var restarted_board_layout: Dictionary = store.latest_snapshot.get("board_layout", {})
	var restarted_units: PackedStringArray = _sorted_keys(restarted_board_layout.get("unit_entities_by_process_id", {}))
	var restarted_lines: PackedStringArray = _sorted_keys(restarted_board_layout.get("line_entities_by_line_id", {}))
	_assert(world_renderer.rendered_unit_ids() == restarted_units,
		"WorldRenderer unit ids must match authoritative restart state")
	_assert(world_renderer.rendered_line_ids() == restarted_lines,
		"WorldRenderer line ids must match authoritative restart state")

	var stop_polling_count_before_teardown: int = int(store.stop_polling_count)
	bootstrap_root.call("_show_title_screen")
	await process_frame
	_assert(int(store.stop_polling_count) > stop_polling_count_before_teardown,
		"Title-screen teardown path must stop polling through BootstrapController")
	_assert(not store.is_polling_active, "Polling must stop cleanly on scene teardown")

	bootstrap_root.queue_free()
	await process_frame
	quit(0)
