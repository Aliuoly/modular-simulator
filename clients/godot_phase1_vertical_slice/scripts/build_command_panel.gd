extends VBoxContainer

@export var session_store_path: NodePath

const BOUNDARY_ANCHORS := {
	"sweet_wet_gas": Vector2(-6.0, 0.0),
	"separator_gas": Vector2(6.5, 1.3),
	"unstabilized_condensate": Vector2(6.5, -1.3),
	"dry_gas": Vector2(8.0, 0.8),
	"ngl_liquids": Vector2(8.0, -0.1),
	"stabilized_condensate": Vector2(8.0, -1.7),
	"feed": Vector2(-6.0, 0.0),
	"vapor_product": Vector2(6.0, 1.0),
	"liquid_product": Vector2(6.0, -1.0),
}
const UNIT_ANCHOR_SPACING_X := 2.0
const KEEP_OUT_HALF_WIDTH := 0.8
const KEEP_OUT_HALF_HEIGHT := 0.65

@onready var status_label: Label = get_node("StatusLabel")
@onready var build_item_label: Label = get_node("BuildItemLabel")
@onready var build_item_next_button: Button = get_node("BuildItemNextButton")
@onready var build_selected_button: Button = get_node("BuildSelectedButton")
@onready var line_source_label: Label = get_node("LineSourceLabel")
@onready var line_source_next_button: Button = get_node("LineSourceNextButton")
@onready var line_target_label: Label = get_node("LineTargetLabel")
@onready var line_target_next_button: Button = get_node("LineTargetNextButton")
@onready var research_status_label: Label = get_node("ResearchStatusLabel")
@onready var submit_research_button: Button = get_node("SubmitResearchButton")
@onready var buy_feed_button: Button = get_node("BuyFeedButton")
@onready var sell_product_button: Button = get_node("SellProductButton")
@onready var restart_button: Button = get_node("RestartButton")

var _session_store: Node
var _available_build_item_ids: Array = []
var _available_research_ids: Array = []
var _source_endpoint_ids: Array = []
var _target_endpoint_ids: Array = []
var _selected_build_index: int = 0
var _selected_source_index: int = -1
var _selected_target_index: int = -1
var _build_counts_by_item_id: Dictionary = {}


func _ready() -> void:
	_session_store = get_node_or_null(session_store_path)
	if _session_store == null:
		status_label.text = "Session store not found"
		return

	build_item_next_button.pressed.connect(_on_build_item_next_pressed)
	build_selected_button.pressed.connect(_on_build_selected_pressed)
	line_source_next_button.pressed.connect(_on_line_source_next_pressed)
	line_target_next_button.pressed.connect(_on_line_target_next_pressed)
	submit_research_button.pressed.connect(_on_submit_research_pressed)
	buy_feed_button.pressed.connect(_on_buy_feed_pressed)
	sell_product_button.pressed.connect(_on_sell_product_pressed)
	restart_button.pressed.connect(_on_restart_pressed)

	if _session_store.has_signal("snapshot_updated"):
		_session_store.snapshot_updated.connect(_on_snapshot_updated)

	if not _session_store.latest_snapshot.is_empty():
		_apply_snapshot(_session_store.latest_snapshot)


func _on_snapshot_updated() -> void:
	_apply_snapshot(_session_store.latest_snapshot)


func _apply_snapshot(snapshot: Dictionary) -> void:
	var simulation_snapshot: Dictionary = _dictionary_or_empty(snapshot.get("simulation_snapshot", {}))
	var progression_snapshot: Dictionary = _dictionary_or_empty(simulation_snapshot.get("progression_snapshot", {}))
	var previous_source_id := _selected_endpoint_id(_source_endpoint_ids, _selected_source_index)
	var previous_target_id := _selected_endpoint_id(_target_endpoint_ids, _selected_target_index)

	if progression_snapshot.is_empty():
		_available_build_item_ids = _array_or_empty(snapshot.get("supported_build_item_ids", []))
		_available_research_ids = []
	else:
		_available_build_item_ids = _array_or_empty(progression_snapshot.get("available_item_ids", []))
		_available_research_ids = _array_or_empty(progression_snapshot.get("available_research_ids", []))

	if _selected_build_index >= _available_build_item_ids.size():
		_selected_build_index = 0

	_refresh_line_endpoint_choices(snapshot)
	_selected_source_index = _index_or_unselected(_source_endpoint_ids, previous_source_id)
	_selected_target_index = _index_or_unselected(_target_endpoint_ids, previous_target_id)

	_update_build_item_label()
	_update_line_endpoint_labels()
	_update_research_label()


func _update_build_item_label() -> void:
	if _available_build_item_ids.is_empty():
		build_item_label.text = "Selected build item: --"
		return
	var item_id := String(_available_build_item_ids[_selected_build_index])
	build_item_label.text = "Selected build item: %s" % item_id


func _update_line_endpoint_labels() -> void:
	line_source_label.text = "Line source: %s" % _selected_endpoint_text(
		_source_endpoint_ids,
		_selected_source_index,
	)
	line_target_label.text = "Line target: %s" % _selected_endpoint_text(
		_target_endpoint_ids,
		_selected_target_index,
	)


func _update_research_label() -> void:
	if _available_research_ids.is_empty():
		research_status_label.text = "Research target: none"
		return
	research_status_label.text = "Research target: %s" % String(_available_research_ids[0])


func _on_build_item_next_pressed() -> void:
	if _available_build_item_ids.is_empty():
		status_label.text = "No build items unlocked"
		return
	_selected_build_index = (_selected_build_index + 1) % _available_build_item_ids.size()
	_update_build_item_label()
	status_label.text = "Selected %s" % String(_available_build_item_ids[_selected_build_index])


func _on_build_selected_pressed() -> void:
	if _available_build_item_ids.is_empty():
		status_label.text = "No build items unlocked"
		return

	var item_id := String(_available_build_item_ids[_selected_build_index])
	if item_id == "build_process_line":
		await _submit_selected_line()
		return

	var count: int = int(_build_counts_by_item_id.get(item_id, 0)) + 1
	_build_counts_by_item_id[item_id] = count
	var process_id := _process_id_for_item(item_id, count)
	var build_result: Dictionary = await _session_store.build_item(
		item_id,
		{"process_id": process_id},
		{"anchor_xy": [float(count) * UNIT_ANCHOR_SPACING_X, 0.0]}
	)

	if bool(build_result.get("ok", false)):
		status_label.text = "Built %s" % item_id
	else:
		status_label.text = "Build failed: %s" % String(build_result.get("error_code", "unknown"))


func _on_line_source_next_pressed() -> void:
	if _source_endpoint_ids.is_empty():
		status_label.text = "No line sources available"
		return
	if _selected_source_index < 0:
		_selected_source_index = 0
	else:
		_selected_source_index = (_selected_source_index + 1) % _source_endpoint_ids.size()
	_update_line_endpoint_labels()
	status_label.text = "Selected line source %s" % _selected_endpoint_id(
		_source_endpoint_ids,
		_selected_source_index,
	)


func _on_line_target_next_pressed() -> void:
	if _target_endpoint_ids.is_empty():
		status_label.text = "No line targets available"
		return
	if _selected_target_index < 0:
		_selected_target_index = 0
	else:
		_selected_target_index = (_selected_target_index + 1) % _target_endpoint_ids.size()
	_update_line_endpoint_labels()
	status_label.text = "Selected line target %s" % _selected_endpoint_id(
		_target_endpoint_ids,
		_selected_target_index,
	)


func _submit_selected_line() -> void:
	var source_id := _selected_endpoint_id(_source_endpoint_ids, _selected_source_index)
	var target_id := _selected_endpoint_id(_target_endpoint_ids, _selected_target_index)
	if source_id == "":
		status_label.text = "Select a line source first"
		return
	if target_id == "":
		status_label.text = "Select a line target first"
		return
	if source_id == target_id:
		status_label.text = "Line source and target must differ"
		return

	var path_xy := _route_line_path(source_id, target_id, _session_store.latest_snapshot)
	if path_xy.size() < 2:
		status_label.text = "No valid orthogonal route found"
		return

	var build_result: Dictionary = await _session_store.build_item(
		"build_process_line",
		{"source": source_id, "target": target_id},
		{"path_xy": path_xy},
	)
	if bool(build_result.get("ok", false)):
		status_label.text = "Built build_process_line: %s -> %s" % [source_id, target_id]
	else:
		status_label.text = "Build failed: %s" % String(build_result.get("error_code", "unknown"))


func _on_submit_research_pressed() -> void:
	if _available_research_ids.is_empty():
		status_label.text = "No research available"
		return

	var research_id := String(_available_research_ids[0])
	var result: Dictionary = await _session_store.submit_research(
		research_id,
		{
			"separator_gas": 20.0,
			"unstabilized_condensate": 10.0,
			"dry_gas": 20.0,
		}
	)
	if bool(result.get("ok", false)):
		status_label.text = "Research submitted: %s" % research_id
	else:
		status_label.text = "Research failed: %s" % String(result.get("error_code", "unknown"))


func _on_buy_feed_pressed() -> void:
	if _session_store != null and String(_session_store.active_mode_id) == "heater_flash_guided_build_v1":
		status_label.text = "Feed purchase unavailable in tutorial"
		return

	var feed_ids := _buy_feed_ids_for_snapshot(_session_store.latest_snapshot)
	var last_error_code := "unknown"
	for feed_id in feed_ids:
		var result: Dictionary = await _session_store.buy_feed(feed_id, 10.0)
		if bool(result.get("ok", false)):
			status_label.text = "Bought %s" % feed_id
			return
		last_error_code = String(result.get("error_code", "unknown"))
	status_label.text = "Buy feed failed: %s" % last_error_code


func _on_sell_product_pressed() -> void:
	var result: Dictionary = await _session_store.sell_product("separator_gas", 1.0)
	if bool(result.get("ok", false)):
		status_label.text = "Sold separator_gas"
	else:
		status_label.text = "Sell product failed: %s" % String(result.get("error_code", "unknown"))


func _on_restart_pressed() -> void:
	var result: Dictionary = await _session_store.restart_session()
	if bool(result.get("ok", false)):
		status_label.text = "Session restarted"
	else:
		status_label.text = "Restart failed: %s" % String(result.get("error_code", "unknown"))


func _refresh_line_endpoint_choices(snapshot: Dictionary) -> void:
	var topology_payload: Dictionary = _dictionary_or_empty(snapshot.get("topology", {}))
	var topology: Dictionary = _dictionary_or_empty(topology_payload.get("topology", {}))
	var nodes: Array = _array_or_empty(topology.get("nodes", []))
	var source_ids: Array = []
	var target_ids: Array = []

	for node_value in nodes:
		var node := _dictionary_or_empty(node_value)
		var node_id := String(node.get("node_id", ""))
		var node_kind := String(node.get("node_kind", "unknown"))
		if node_id == "":
			continue

		var ports: Array = _array_or_empty(node.get("ports", []))
		for port_value in ports:
			var port_data := _dictionary_or_empty(port_value)
			var port_name := String(port_data.get("port_name", ""))
			var direction := String(port_data.get("direction", "unknown"))
			if port_name == "":
				continue
			if node_kind == "boundary":
				if direction == "source":
					_append_unique(source_ids, node_id)
				elif direction == "sink":
					_append_unique(target_ids, node_id)
				continue

			var endpoint_id := "%s.%s" % [node_id, port_name]
			if direction == "inlet":
				_append_unique(target_ids, endpoint_id)
			elif direction == "outlet":
				_append_unique(source_ids, endpoint_id)

	source_ids.sort()
	target_ids.sort()
	_source_endpoint_ids = source_ids
	_target_endpoint_ids = target_ids


func _route_line_path(source_id: String, target_id: String, snapshot: Dictionary) -> Array:
	var source_anchor: Variant = _endpoint_anchor(source_id, snapshot)
	var target_anchor: Variant = _endpoint_anchor(target_id, snapshot)
	if not (source_anchor is Vector2) or not (target_anchor is Vector2):
		return []

	var excluded_process_ids := PackedStringArray()
	var source_process_id := _process_id_for_endpoint(source_id)
	var target_process_id := _process_id_for_endpoint(target_id)
	if source_process_id != "":
		excluded_process_ids.append(source_process_id)
	if target_process_id != "":
		excluded_process_ids.append(target_process_id)
	var keepouts := _unit_keepouts(snapshot, excluded_process_ids)
	var source_point: Vector2 = source_anchor
	var target_point: Vector2 = target_anchor

	var top_lane: float = minf(source_point.y, target_point.y) - 1.2
	var bottom_lane: float = maxf(source_point.y, target_point.y) + 1.2
	var left_lane: float = minf(source_point.x, target_point.x) - 1.5
	var right_lane: float = maxf(source_point.x, target_point.x) + 1.5
	for keepout_value in keepouts:
		var keepout: Dictionary = _dictionary_or_empty(keepout_value)
		top_lane = minf(top_lane, float(keepout.get("min_y", top_lane)) - 0.8)
		bottom_lane = maxf(bottom_lane, float(keepout.get("max_y", bottom_lane)) + 0.8)
		left_lane = minf(left_lane, float(keepout.get("min_x", left_lane)) - 0.8)
		right_lane = maxf(right_lane, float(keepout.get("max_x", right_lane)) + 0.8)

	var candidate_paths := [
		[source_point, Vector2(target_point.x, source_point.y), target_point],
		[source_point, Vector2(source_point.x, target_point.y), target_point],
		[source_point, Vector2(source_point.x, top_lane), Vector2(target_point.x, top_lane), target_point],
		[source_point, Vector2(source_point.x, bottom_lane), Vector2(target_point.x, bottom_lane), target_point],
		[source_point, Vector2(left_lane, source_point.y), Vector2(left_lane, target_point.y), target_point],
		[source_point, Vector2(right_lane, source_point.y), Vector2(right_lane, target_point.y), target_point],
	]

	for candidate in candidate_paths:
		var normalized := _normalize_path(candidate)
		if normalized.size() < 2:
			continue
		if _path_clears_keepouts(normalized, keepouts):
			return _vector_path_to_payload(normalized)
	return []


func _endpoint_anchor(endpoint_id: String, snapshot: Dictionary) -> Variant:
	if BOUNDARY_ANCHORS.has(endpoint_id):
		return BOUNDARY_ANCHORS[endpoint_id]

	var separator_index := endpoint_id.find(".")
	if separator_index <= 0:
		return null
	var process_id := endpoint_id.substr(0, separator_index)
	var port_name := endpoint_id.substr(separator_index + 1)
	var board_layout: Dictionary = _dictionary_or_empty(snapshot.get("board_layout", {}))
	var unit_entities: Dictionary = _dictionary_or_empty(board_layout.get("unit_entities_by_process_id", {}))
	var entity: Dictionary = _dictionary_or_empty(unit_entities.get(process_id, {}))
	var anchor_xy: Array = _array_or_empty(entity.get("anchor_xy", []))
	if anchor_xy.size() != 2:
		return null
	var process_anchor := Vector2(float(anchor_xy[0]), float(anchor_xy[1]))
	return process_anchor + _port_offset(port_name)


func _port_offset(port_name: String) -> Vector2:
	match port_name:
		"inlet":
			return Vector2(-1.05, 0.0)
		"hot_inlet":
			return Vector2(-1.05, 0.35)
		"cold_inlet":
			return Vector2(-1.05, -0.35)
		"outlet":
			return Vector2(1.05, 0.0)
		"outlet_1":
			return Vector2(1.05, 0.28)
		"outlet_2":
			return Vector2(1.05, -0.28)
		"vapor_outlet":
			return Vector2(1.05, 0.4)
		"liquid_outlet":
			return Vector2(1.05, -0.4)
		"hot_outlet":
			return Vector2(1.05, 0.35)
		"cold_outlet":
			return Vector2(1.05, -0.35)
		_:
			return Vector2(1.05, 0.0)


func _unit_keepouts(snapshot: Dictionary, excluded_process_ids: PackedStringArray) -> Array:
	var keepouts: Array = []
	var board_layout: Dictionary = _dictionary_or_empty(snapshot.get("board_layout", {}))
	var unit_entities: Dictionary = _dictionary_or_empty(board_layout.get("unit_entities_by_process_id", {}))
	for process_id in unit_entities.keys():
		var process_id_text := String(process_id)
		if excluded_process_ids.has(process_id_text):
			continue
		var entity: Dictionary = _dictionary_or_empty(unit_entities.get(process_id, {}))
		var anchor_xy: Array = _array_or_empty(entity.get("anchor_xy", []))
		if anchor_xy.size() != 2:
			continue
		var center := Vector2(float(anchor_xy[0]), float(anchor_xy[1]))
		keepouts.append(
			{
				"min_x": center.x - KEEP_OUT_HALF_WIDTH,
				"max_x": center.x + KEEP_OUT_HALF_WIDTH,
				"min_y": center.y - KEEP_OUT_HALF_HEIGHT,
				"max_y": center.y + KEEP_OUT_HALF_HEIGHT,
			}
		)
	return keepouts


func _normalize_path(points: Array) -> Array:
	var normalized: Array = []
	for point_value in points:
		if not (point_value is Vector2):
			continue
		var point: Vector2 = point_value
		if normalized.is_empty() or (normalized[-1] as Vector2) != point:
			normalized.append(point)
	if normalized.size() < 3:
		return normalized
	var simplified: Array = [normalized[0]]
	for index in range(1, normalized.size() - 1):
		var previous: Vector2 = simplified[-1]
		var current: Vector2 = normalized[index]
		var following: Vector2 = normalized[index + 1]
		if (is_equal_approx(previous.x, current.x) and is_equal_approx(current.x, following.x)) \
		or (is_equal_approx(previous.y, current.y) and is_equal_approx(current.y, following.y)):
			continue
		simplified.append(current)
	simplified.append(normalized[-1])
	return simplified


func _path_clears_keepouts(path_points: Array, keepouts: Array) -> bool:
	for index in range(path_points.size() - 1):
		var start: Vector2 = path_points[index]
		var finish: Vector2 = path_points[index + 1]
		if not _segment_clears_keepouts(start, finish, keepouts):
			return false
	return true


func _segment_clears_keepouts(start: Vector2, finish: Vector2, keepouts: Array) -> bool:
	var horizontal := is_equal_approx(start.y, finish.y)
	var vertical := is_equal_approx(start.x, finish.x)
	if not horizontal and not vertical:
		return false
	for keepout_value in keepouts:
		var keepout: Dictionary = _dictionary_or_empty(keepout_value)
		if keepout.is_empty():
			continue
		if horizontal:
			var y := start.y
			if y <= float(keepout.get("min_y", y)) or y >= float(keepout.get("max_y", y)):
				continue
			var segment_min_x: float = minf(start.x, finish.x)
			var segment_max_x: float = maxf(start.x, finish.x)
			if segment_max_x > float(keepout.get("min_x", segment_max_x)) and segment_min_x < float(keepout.get("max_x", segment_min_x)):
				return false
		else:
			var x := start.x
			if x <= float(keepout.get("min_x", x)) or x >= float(keepout.get("max_x", x)):
				continue
			var segment_min_y: float = minf(start.y, finish.y)
			var segment_max_y: float = maxf(start.y, finish.y)
			if segment_max_y > float(keepout.get("min_y", segment_max_y)) and segment_min_y < float(keepout.get("max_y", segment_min_y)):
				return false
	return true


func _vector_path_to_payload(path_points: Array) -> Array:
	var payload: Array = []
	for point_value in path_points:
		var point: Vector2 = point_value
		payload.append([point.x, point.y])
	return payload


func _selected_endpoint_text(endpoint_ids: Array, selected_index: int) -> String:
	var endpoint_id := _selected_endpoint_id(endpoint_ids, selected_index)
	if endpoint_id == "":
		return "--"
	return endpoint_id


func _selected_endpoint_id(endpoint_ids: Array, selected_index: int) -> String:
	if selected_index < 0 or selected_index >= endpoint_ids.size():
		return ""
	return String(endpoint_ids[selected_index])


func _index_or_unselected(endpoint_ids: Array, endpoint_id: String) -> int:
	if endpoint_id == "":
		return -1
	return endpoint_ids.find(endpoint_id)


func _append_unique(values: Array, value: String) -> void:
	if not values.has(value):
		values.append(value)


func _process_id_for_endpoint(endpoint_id: String) -> String:
	var separator_index := endpoint_id.find(".")
	if separator_index <= 0:
		return ""
	return endpoint_id.substr(0, separator_index)


func _process_id_for_item(item_id: String, count: int) -> String:
	match item_id:
		"place_inlet_gas_separator":
			return "separator_%d" % count
		"place_teg_contactor":
			return "contactor_%d" % count
		"place_rich_glycol_flash_tank":
			return "rich_flash_%d" % count
		"place_lean_rich_glycol_exchanger":
			return "lean_rich_exchanger_%d" % count
		"place_teg_regenerator":
			return "regenerator_%d" % count
		"place_gas_gas_exchanger":
			return "gas_gas_exchanger_%d" % count
		"place_low_temperature_separator":
			return "low_temp_separator_%d" % count
		"place_condensate_stabilizer":
			return "stabilizer_%d" % count
		_:
			return "%s_%d" % [item_id.replace("place_", "").replace("install_", ""), count]


func _feed_id_for_snapshot(snapshot: Dictionary) -> String:
	var simulation_snapshot: Dictionary = _dictionary_or_empty(snapshot.get("simulation_snapshot", {}))
	var feed_inventory: Dictionary = _dictionary_or_empty(simulation_snapshot.get("feed_inventory_by_material_id", {}))
	for feed_id in feed_inventory.keys():
		return String(feed_id)
	return "sweet_wet_gas"


func _buy_feed_ids_for_snapshot(snapshot: Dictionary) -> Array:
	var primary_feed_id := _feed_id_for_snapshot(snapshot)
	if primary_feed_id == "feed":
		return ["feed", "sweet_wet_gas"]
	return ["sweet_wet_gas", "feed"]


func _dictionary_or_empty(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value
	return {}


func _array_or_empty(value: Variant) -> Array:
	if value is Array:
		return value
	return []
