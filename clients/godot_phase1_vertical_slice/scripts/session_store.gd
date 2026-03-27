extends Node

signal bootstrap_updated
signal snapshot_updated

@export var backend_client_path: NodePath = NodePath("../BackendClient")

var backend_client: Node
var bootstrap_data: Dictionary = {}
var latest_snapshot: Dictionary = {}
var active_session_id: String = ""
var active_mode_id: String = ""


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
	var create_result: Dictionary = await backend_client.create_session(mode_id)
	if not bool(create_result.get("ok", false)):
		return false

	var payload: Dictionary = create_result.get("payload", {})
	active_mode_id = mode_id
	active_session_id = String(payload.get("session_id", ""))
	latest_snapshot = payload.get("snapshot", {})
	snapshot_updated.emit()
	return active_session_id != ""


func refresh_snapshot() -> bool:
	if active_session_id == "":
		return false
	var snapshot_result: Dictionary = await backend_client.get_snapshot(active_session_id)
	if not bool(snapshot_result.get("ok", false)):
		return false
	latest_snapshot = snapshot_result.get("payload", {})
	snapshot_updated.emit()
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
		latest_snapshot = result.get("payload", {}).get("snapshot", latest_snapshot)
		snapshot_updated.emit()
	return result


func build_item(item_id: String, config: Dictionary = {}, layout: Dictionary = {}) -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.build(active_session_id, item_id, config, layout)
	if bool(result.get("ok", false)):
		latest_snapshot = result.get("payload", {}).get("snapshot", latest_snapshot)
		snapshot_updated.emit()
	return result


func buy_feed(material_id: String, quantity_mol: float) -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.buy_feed(active_session_id, material_id, quantity_mol)
	if bool(result.get("ok", false)):
		latest_snapshot = result.get("payload", {}).get("snapshot", latest_snapshot)
		snapshot_updated.emit()
	return result


func sell_product(product_id: String, quantity_mol: float) -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.sell_product(active_session_id, product_id, quantity_mol)
	if bool(result.get("ok", false)):
		latest_snapshot = result.get("payload", {}).get("snapshot", latest_snapshot)
		snapshot_updated.emit()
	return result


func restart_session() -> Dictionary:
	if active_session_id == "":
		return {"ok": false, "error_code": "no_active_session", "message": "No active session"}
	var result: Dictionary = await backend_client.restart(active_session_id)
	if bool(result.get("ok", false)):
		latest_snapshot = result.get("payload", {}).get("snapshot", latest_snapshot)
		snapshot_updated.emit()
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
	# No background polling in this narrow slice.
	pass
