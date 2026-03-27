extends VBoxContainer

@export var session_store_path: NodePath

@onready var status_label: Label = get_node("StatusLabel")
@onready var build_item_label: Label = get_node("BuildItemLabel")
@onready var build_item_next_button: Button = get_node("BuildItemNextButton")
@onready var build_selected_button: Button = get_node("BuildSelectedButton")
@onready var research_status_label: Label = get_node("ResearchStatusLabel")
@onready var submit_research_button: Button = get_node("SubmitResearchButton")
@onready var buy_feed_button: Button = get_node("BuyFeedButton")
@onready var sell_product_button: Button = get_node("SellProductButton")
@onready var restart_button: Button = get_node("RestartButton")

var _session_store: Node
var _available_build_item_ids: Array = []
var _available_research_ids: Array = []
var _selected_build_index: int = 0
var _build_counts_by_item_id: Dictionary = {}


func _ready() -> void:
	_session_store = get_node_or_null(session_store_path)
	if _session_store == null:
		status_label.text = "Session store not found"
		return

	build_item_next_button.pressed.connect(_on_build_item_next_pressed)
	build_selected_button.pressed.connect(_on_build_selected_pressed)
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
	var simulation_snapshot: Dictionary = snapshot.get("simulation_snapshot", {})
	var progression_snapshot: Dictionary = simulation_snapshot.get("progression_snapshot", {})

	if progression_snapshot.is_empty():
		_available_build_item_ids = snapshot.get("supported_build_item_ids", [])
		_available_research_ids = []
	else:
		_available_build_item_ids = progression_snapshot.get("available_item_ids", [])
		_available_research_ids = progression_snapshot.get("available_research_ids", [])

	if _selected_build_index >= _available_build_item_ids.size():
		_selected_build_index = 0

	_update_build_item_label()
	_update_research_label()


func _update_build_item_label() -> void:
	if _available_build_item_ids.is_empty():
		build_item_label.text = "Selected build item: --"
		return
	var item_id := String(_available_build_item_ids[_selected_build_index])
	build_item_label.text = "Selected build item: %s" % item_id


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
		status_label.text = "Line build requires explicit endpoints"
		return

	var count: int = int(_build_counts_by_item_id.get(item_id, 0)) + 1
	_build_counts_by_item_id[item_id] = count
	var process_id := _process_id_for_item(item_id, count)
	var build_result: Dictionary = await _session_store.build_item(
		item_id,
		{"process_id": process_id},
		{"anchor_xy": [float(count), 0.0]}
	)

	if bool(build_result.get("ok", false)):
		status_label.text = "Built %s" % item_id
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
	var result: Dictionary = await _session_store.buy_feed("sweet_wet_gas", 10.0)
	if bool(result.get("ok", false)):
		status_label.text = "Bought sweet_wet_gas"
	else:
		status_label.text = "Buy feed failed: %s" % String(result.get("error_code", "unknown"))


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
