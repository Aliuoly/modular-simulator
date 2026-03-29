extends Control

@export var session_store_path: NodePath

@onready var mode_label: Label = get_node("VBox/ModeLabel")
@onready var cash_label: Label = get_node("VBox/CashLabel")
@onready var feed_label: Label = get_node("VBox/FeedLabel")
@onready var product_label: Label = get_node("VBox/ProductLabel")
@onready var signals_label: Label = get_node("VBox/SignalsLabel")
@onready var stage_label: Label = get_node("VBox/StageLabel")
@onready var research_label: Label = get_node("VBox/ResearchLabel")
@onready var unlocked_items_label: Label = get_node("VBox/UnlockedItemsLabel")
@onready var goals_label: Label = get_node("VBox/GoalsLabel")
@onready var lag_label: Label = get_node("VBox/LagLabel")
@onready var error_label: Label = get_node("VBox/ErrorLabel")

var _session_store: Node


func _ready() -> void:
	_session_store = get_node_or_null(session_store_path)
	if _session_store == null:
		error_label.text = "Session store not found"
		return

	if _session_store.has_signal("snapshot_updated"):
		_session_store.snapshot_updated.connect(_on_snapshot_updated)

	if not _session_store.latest_snapshot.is_empty():
		_render_snapshot(_session_store.latest_snapshot)


func _on_snapshot_updated() -> void:
	_render_snapshot(_session_store.latest_snapshot)


func _render_snapshot(snapshot: Dictionary) -> void:
	mode_label.text = "Mode: %s" % String(snapshot.get("mode_id", "--"))

	var cash_ledger: Dictionary = _dictionary_or_empty(snapshot.get("cash_ledger", {}))
	cash_label.text = "Cash: %.2f" % float(cash_ledger.get("cash_balance", 0.0))

	var simulation_snapshot: Dictionary = _dictionary_or_empty(snapshot.get("simulation_snapshot", {}))
	feed_label.text = "Feed: %s" % _format_inventory(
		simulation_snapshot.get("feed_inventory_by_material_id", {})
	)
	product_label.text = "Product: %s" % _format_inventory(
		simulation_snapshot.get("product_inventory_by_product_id", {})
	)
	signals_label.text = "Signals: %s" % _format_inventory(
		snapshot.get("published_signal_values_by_id", {})
	)

	var progression_snapshot: Dictionary = _dictionary_or_empty(simulation_snapshot.get("progression_snapshot", {}))
	if progression_snapshot.is_empty():
		stage_label.text = "Stage: --"
		research_label.text = "Research: --"
		unlocked_items_label.text = "Unlocked Build Items: --"
	else:
		stage_label.text = "Stage: %s" % String(progression_snapshot.get("active_stage_id", "--"))
		research_label.text = "Research: %s" % _format_sequence(
			progression_snapshot.get("available_research_ids", [])
		)
		unlocked_items_label.text = "Unlocked Build Items: %s" % _format_sequence(
			progression_snapshot.get("available_item_ids", [])
		)

	var goals := PackedStringArray()
	if _session_store != null and _session_store.has_method("tutorial_goal_summary_lines"):
		goals = _session_store.tutorial_goal_summary_lines()
	goals_label.text = "Tutorial Goals: %s" % (", ".join(goals) if goals.size() > 0 else "--")

	lag_label.text = "Lag: %.3fs" % float(snapshot.get("lag_backlog_s", 0.0))
	error_label.text = ""


func _format_inventory(values: Variant) -> String:
	if values is Dictionary:
		var parts := PackedStringArray()
		for key in values.keys():
			parts.append("%s=%.2f" % [String(key), float(values[key])])
		parts.sort()
		return ", ".join(parts)
	return "--"


func _format_sequence(values: Variant) -> String:
	if values is Array:
		if values.is_empty():
			return "none"
		var texts := PackedStringArray()
		for value in values:
			texts.append(String(value))
		return ", ".join(texts)
	return "--"


func _dictionary_or_empty(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value
	return {}
