extends Node3D

@export var session_store_path: NodePath

var _session_store: Node


func _ready() -> void:
	_session_store = get_node_or_null(session_store_path)
	if _session_store != null and _session_store.has_signal("snapshot_updated"):
		_session_store.snapshot_updated.connect(_on_snapshot_updated)


func _on_snapshot_updated() -> void:
	# Keep the world slice intentionally minimal; the smoke harness asserts
	# wiring and state propagation, not detailed mesh/asset rendering.
	pass
