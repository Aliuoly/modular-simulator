extends Node

signal bootstrap_updated
signal snapshot_updated

@export var backend_client_path: NodePath = NodePath("../BackendClient")

const POLL_INTERVAL_S := 0.6

var backend_client: Node
var bootstrap_data: Dictionary = {}
var latest_snapshot: Dictionary = {}
var active_session_id: String = ""
var active_mode_id: String = ""
var is_polling_active: bool = false
var poll_success_count: int = 0
var stop_polling_count: int = 0
var snapshot_update_count: int = 0
var last_snapshot_update_source: String = ""
var _poll_generation: int = 0


func _ready() -> void:
	backend_client = get_node_or_null(backend_client_path)


func set_backend_client(client: Node) -> void:
	backend_client = client


func load_bootstrap() -> bool:
	var result: Dictionary = await backend_client.get_bootstrap()
	if not bool(result.get("ok", false)):
		return false
	bootstrap_data = result.get("payload", {})
	bootstrap_updated.emit()
	return true


func supported_mode_ids() -> Array:
	var modes: Variant = bootstrap_data.get("supported_mode_ids", [])
	if modes is Array:
		return modes
	return []


func start_mode(mode_id: String) -> bool:
	stop_polling()
	var create_result: Dictionary = await backend_client.create_session(mode_id)
	if not bool(create_result.get("ok", false)):
		return false

	var payload: Dictionary = create_result.get("payload", {})
	active_mode_id = mode_id
	active_session_id = String(payload.get("session_id", ""))
	_apply_authoritative_snapshot(payload.get("snapshot", {}), "session_start")
	if active_session_id != "":
		_start_polling()
	return active_session_id != ""


func refresh_snapshot() -> bool:
	return await _refresh_snapshot_with_source("manual")


func _refresh_snapshot_with_source(source: String, generation: int = -1) -> bool:
	if active_session_id == "":
		return false
	var requested_session_id := active_session_id
	var snapshot_result: Dictionary = await backend_client.get_snapshot(requested_session_id)
	if not bool(snapshot_result.get("ok", false)):
		return false
	if source == "poll":
		if generation != _poll_generation or not is_polling_active or requested_session_id != active_session_id:
			return false
		poll_success_count += 1
	_apply_authoritative_snapshot(snapshot_result.get("payload", {}), source)
	return true


func submit_research(research_id: String, submitted_quantities_by_product_id: Dictionary) -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.submit_research(
		active_session_id,
		research_id,
		submitted_quantities_by_product_id,
	)
	if bool(result.get("ok", false)):
		_apply_authoritative_snapshot(result.get("payload", {}).get("snapshot", latest_snapshot), "command:research")
	return result


func build_item(item_id: String, config: Dictionary = {}, layout: Dictionary = {}) -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.build(active_session_id, item_id, config, layout)
	if bool(result.get("ok", false)):
		_apply_authoritative_snapshot(result.get("payload", {}).get("snapshot", latest_snapshot), "command:build")
	return result


func buy_feed(material_id: String, quantity_mol: float) -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.buy_feed(active_session_id, material_id, quantity_mol)
	if bool(result.get("ok", false)):
		_apply_authoritative_snapshot(result.get("payload", {}).get("snapshot", latest_snapshot), "command:buy_feed")
	return result


func sell_product(product_id: String, quantity_mol: float) -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.sell_product(active_session_id, product_id, quantity_mol)
	if bool(result.get("ok", false)):
		_apply_authoritative_snapshot(result.get("payload", {}).get("snapshot", latest_snapshot), "command:sell_product")
	return result


func restart_session() -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.restart(active_session_id)
	if bool(result.get("ok", false)):
		_apply_authoritative_snapshot(result.get("payload", {}).get("snapshot", latest_snapshot), "command:restart")
	return result


func tutorial_goal_summary_lines() -> PackedStringArray:
	var lines := PackedStringArray()
	var simulation_snapshot: Dictionary = latest_snapshot.get("simulation_snapshot", {})
	var goals: Variant = simulation_snapshot.get("tutorial_goal_status_by_id", {})
	if goals is Dictionary:
		for goal_id in goals.keys():
			var goal_data: Variant = goals[goal_id]
			if goal_data is Dictionary and bool(goal_data.get("completed", false)):
				lines.append("%s: done" % String(goal_id))
			elif goal_data is Dictionary:
				lines.append("%s: pending" % String(goal_id))
	return lines


func product_inventory() -> Dictionary:
	var simulation_snapshot: Dictionary = latest_snapshot.get("simulation_snapshot", {})
	var products: Variant = simulation_snapshot.get("product_inventory_by_product_id", {})
	if products is Dictionary:
		return products
	return {}


func stop_polling() -> void:
	stop_polling_count += 1
	is_polling_active = false
	_poll_generation += 1


func _apply_authoritative_snapshot(snapshot: Variant, source: String) -> void:
	if snapshot is Dictionary:
		latest_snapshot = snapshot
	else:
		latest_snapshot = {}
	last_snapshot_update_source = source
	snapshot_update_count += 1
	snapshot_updated.emit()


func _start_polling() -> void:
	if active_session_id == "":
		return
	_poll_generation += 1
	is_polling_active = true
	_poll_loop(_poll_generation)


func _poll_loop(generation: int) -> void:
	while generation == _poll_generation and is_polling_active and active_session_id != "":
		var timer := get_tree().create_timer(POLL_INTERVAL_S)
		await timer.timeout
		if generation != _poll_generation or not is_polling_active or active_session_id == "":
			return
		await _refresh_snapshot_with_source("poll", generation)
