extends Node3D

@export var session_store_path: NodePath

const BOUNDARY_ANCHORS := {
	"sweet_wet_gas": Vector3(-6.0, 0.35, 0.0),
	"separator_gas": Vector3(6.5, 0.35, 1.3),
	"unstabilized_condensate": Vector3(6.5, 0.35, -1.3),
	"dry_gas": Vector3(8.0, 0.35, 0.8),
	"ngl_liquids": Vector3(8.0, 0.35, -0.1),
	"stabilized_condensate": Vector3(8.0, 0.35, -1.7),
	"feed": Vector3(-6.0, 0.35, 0.0),
	"vapor_product": Vector3(6.0, 0.35, 1.0),
	"liquid_product": Vector3(6.0, 0.35, -1.0),
}

var _session_store: Node
var _units_root: Node3D
var _lines_root: Node3D
var _boundaries_root: Node3D


func _ready() -> void:
	_ensure_render_roots()
	_session_store = get_node_or_null(session_store_path)
	if _session_store != null and _session_store.has_signal("snapshot_updated"):
		_session_store.snapshot_updated.connect(_on_snapshot_updated)
	if _session_store != null and not _session_store.latest_snapshot.is_empty():
		_render_snapshot(_session_store.latest_snapshot)


func rendered_unit_ids() -> PackedStringArray:
	return _rendered_ids(_units_root)


func rendered_line_ids() -> PackedStringArray:
	return _rendered_ids(_lines_root)


func rendered_boundary_ids() -> PackedStringArray:
	return _rendered_ids(_boundaries_root)


func _on_snapshot_updated() -> void:
	_render_snapshot(_session_store.latest_snapshot)


func _render_snapshot(snapshot: Dictionary) -> void:
	_ensure_render_roots()
	_clear_render_root(_units_root)
	_clear_render_root(_lines_root)
	_clear_render_root(_boundaries_root)
	_render_units(snapshot)
	_render_lines(snapshot)
	_render_boundaries(snapshot)


func _render_units(snapshot: Dictionary) -> void:
	var board_layout: Dictionary = _dictionary_or_empty(snapshot.get("board_layout", {}))
	var unit_entities: Dictionary = _dictionary_or_empty(board_layout.get("unit_entities_by_process_id", {}))
	for process_id_variant in unit_entities.keys():
		var process_id := String(process_id_variant)
		var entity: Dictionary = _dictionary_or_empty(unit_entities.get(process_id_variant, {}))
		var anchor_xy: Array = _array_or_empty(entity.get("anchor_xy", []))
		if anchor_xy.size() != 2:
			continue
		var marker := MeshInstance3D.new()
		marker.name = process_id
		marker.mesh = _unit_mesh()
		marker.material_override = _make_material(Color(0.35, 0.72, 1.0, 1.0))
		marker.transform.origin = Vector3(float(anchor_xy[0]), 0.45, float(anchor_xy[1]))
		_units_root.add_child(marker)


func _render_lines(snapshot: Dictionary) -> void:
	var board_layout: Dictionary = _dictionary_or_empty(snapshot.get("board_layout", {}))
	var line_entities: Dictionary = _dictionary_or_empty(board_layout.get("line_entities_by_line_id", {}))
	for line_id_variant in line_entities.keys():
		var line_id := String(line_id_variant)
		var entity: Dictionary = _dictionary_or_empty(line_entities.get(line_id_variant, {}))
		var path_xy: Array = _array_or_empty(entity.get("path_xy", []))
		if path_xy.size() < 2:
			continue
		var line_root := Node3D.new()
		line_root.name = line_id
		_lines_root.add_child(line_root)
		for index in range(path_xy.size() - 1):
			var start_xy: Array = _array_or_empty(path_xy[index])
			var finish_xy: Array = _array_or_empty(path_xy[index + 1])
			if start_xy.size() != 2 or finish_xy.size() != 2:
				continue
			var start := Vector3(float(start_xy[0]), 0.1, float(start_xy[1]))
			var finish := Vector3(float(finish_xy[0]), 0.1, float(finish_xy[1]))
			var segment := _make_line_segment(start, finish)
			segment.name = "segment_%d" % index
			line_root.add_child(segment)


func _render_boundaries(snapshot: Dictionary) -> void:
	var topology_envelope: Dictionary = _dictionary_or_empty(snapshot.get("topology", {}))
	var topology: Dictionary = _dictionary_or_empty(topology_envelope.get("topology", {}))
	var nodes: Array = _array_or_empty(topology.get("nodes", []))
	for node_value in nodes:
		var node: Dictionary = _dictionary_or_empty(node_value)
		if String(node.get("node_kind", "")) != "boundary":
			continue
		var node_id := String(node.get("node_id", ""))
		if not BOUNDARY_ANCHORS.has(node_id):
			continue
		var marker := MeshInstance3D.new()
		marker.name = node_id
		marker.mesh = _boundary_mesh()
		marker.material_override = _make_material(Color(1.0, 0.78, 0.3, 1.0))
		marker.transform.origin = BOUNDARY_ANCHORS[node_id]
		_boundaries_root.add_child(marker)


func _make_line_segment(start: Vector3, finish: Vector3) -> MeshInstance3D:
	var segment := MeshInstance3D.new()
	segment.mesh = _line_mesh(start.distance_to(finish))
	segment.material_override = _make_material(Color(0.55, 0.9, 0.55, 1.0))
	segment.transform.origin = (start + finish) * 0.5
	if is_equal_approx(start.x, finish.x):
		segment.rotation.y = PI * 0.5
	return segment


func _ensure_render_roots() -> void:
	_units_root = _ensure_root("RenderedUnits")
	_lines_root = _ensure_root("RenderedLines")
	_boundaries_root = _ensure_root("RenderedBoundaries")


func _ensure_root(name: String) -> Node3D:
	var existing := get_node_or_null(name)
	if existing is Node3D:
		return existing
	var root := Node3D.new()
	root.name = name
	add_child(root)
	return root


func _clear_render_root(root: Node3D) -> void:
	for child in root.get_children():
		root.remove_child(child)
		child.queue_free()


func _rendered_ids(root: Node3D) -> PackedStringArray:
	var ids := PackedStringArray()
	for child in root.get_children():
		ids.append(String(child.name))
	ids.sort()
	return ids


func _unit_mesh() -> BoxMesh:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(1.25, 0.7, 0.8)
	return mesh


func _boundary_mesh() -> BoxMesh:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.35, 0.7, 0.35)
	return mesh


func _line_mesh(length: float) -> BoxMesh:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(maxf(length, 0.05), 0.08, 0.08)
	return mesh


func _make_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return material


func _dictionary_or_empty(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value
	return {}


func _array_or_empty(value: Variant) -> Array:
	if value is Array:
		return value
	return []
