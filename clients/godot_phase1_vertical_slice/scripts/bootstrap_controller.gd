extends Node

const TITLE_SCENE := preload("res://scenes/TitleScreen.tscn")
const MAIN_SCENE := preload("res://scenes/MainGame.tscn")

@export var backend_client_path: NodePath = NodePath("BackendClient")
@export var session_store_path: NodePath = NodePath("SessionStore")
@export var screen_root_path: NodePath = NodePath("ScreenRoot")

var _backend_client: Node
var _session_store: Node
var _screen_root: Node


func _ready() -> void:
	_backend_client = get_node_or_null(backend_client_path)
	_session_store = get_node_or_null(session_store_path)
	_screen_root = get_node_or_null(screen_root_path)

	if _backend_client == null or _session_store == null or _screen_root == null:
		return

	_backend_client.configure_from_environment()
	_session_store.set_backend_client(_backend_client)

	var loaded: bool = await _session_store.load_bootstrap()
	if not loaded:
		return

	_show_title_screen()


func _show_title_screen() -> void:
	_clear_screen_root(true)
	var title_screen := TITLE_SCENE.instantiate()
	title_screen.mode_selected.connect(_on_mode_selected)
	_screen_root.add_child(title_screen)


func _on_mode_selected(mode_id: String) -> void:
	var started: bool = await _session_store.start_mode(mode_id)
	if not started:
		return
	_show_main_game()


func _show_main_game() -> void:
	_clear_screen_root(false)
	var main_game := MAIN_SCENE.instantiate()
	_screen_root.add_child(main_game)


func _clear_screen_root(stop_polling: bool) -> void:
	if stop_polling and _session_store != null and _session_store.has_method("stop_polling"):
		_session_store.stop_polling()
	for child in _screen_root.get_children():
		child.queue_free()
