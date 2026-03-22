## Smoke harness for the Phase-1 vertical slice Godot client.
##
## Exercises the real production wiring:
##   Bootstrap → TitleScreen (via BootstrapController._ready)
##   mode_selected signal → session creation → MainGame added by BootstrapController
##   SessionStore.snapshot_updated signal → HUD label update (not a direct call)
##
## Both supported modes are validated by bootstrap discovery, and one supported
## mode is exercised per run via MODSIM_GODOT_SMOKE_MODE:
##   - phase1_process_sandbox_v1  (default)
##   - heater_flash_guided_build_v1  (set MODSIM_GODOT_SMOKE_MODE to run it)
##
## The harness is designed to be correct and inspectable in headless Godot.
## It does NOT fake success: if the backend is unavailable the assertions will
## surface the real failure reason via push_error / quit(1).
##
## Timing notes:
##   BootstrapController._ready() is async (awaits load_bootstrap).  We await
##   SessionStore.bootstrap_updated before proceeding.
##
##   BootstrapController._on_mode_selected() awaits start_mode() (which emits
##   snapshot_updated from the create-session response) *before* calling
##   _show_main_game(), so the initial snapshot fires before the HUD exists.
##   After _show_main_game() the HUD _ready() connects to snapshot_updated.
##   We then call store.refresh_snapshot() to fire a new snapshot_updated that
##   the HUD is already listening for, proving the signal-path is wired.

extends SceneTree

const BOOTSTRAP_SCENE := preload("res://scenes/Bootstrap.tscn")
const DEFAULT_SMOKE_MODE := "phase1_process_sandbox_v1"


func _init() -> void:
	call_deferred("_run")


func _assert(condition: bool, message: String) -> void:
	if not condition:
		push_error("SMOKE ASSERTION FAILED: %s" % message)
		quit(1)


## ── helpers ──────────────────────────────────────────────────────────────────

## Instantiate and add Bootstrap.tscn so that Bootstrap is accessible at the
## NodePath /root/Bootstrap that MainGame's HUD and WorldRenderer expect.
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


## Await SessionStore.bootstrap_updated if bootstrap has not yet been loaded.
## BootstrapController._ready() is async and emits this signal on success.
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


## Return the TitleScreenController that BootstrapController added to ScreenRoot,
## or null if it is not present yet.
func _find_active_title_screen(bootstrap_root: Node) -> Node:
	var screen_root: Node = bootstrap_root.get_node_or_null("ScreenRoot")
	_assert(screen_root != null, "ScreenRoot Control must exist on Bootstrap")
	for child in screen_root.get_children():
		if child.has_signal("mode_selected") and child.has_method("_on_sandbox_pressed"):
			return child
	return null


## Await the next snapshot_updated from the given store and return the snapshot.
func _wait_for_snapshot(store: Node) -> Dictionary:
	await store.snapshot_updated
	return store.latest_snapshot


func _selected_mode_id() -> String:
	var requested: String = OS.get_environment("MODSIM_GODOT_SMOKE_MODE").strip_edges()
	if requested == "":
		return DEFAULT_SMOKE_MODE
	return requested


## Return the first non-TitleScreenController child in ScreenRoot (i.e. MainGame).
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


func _wait_for_goal_or_product(store: Node, mode_id: String, max_frames: int = 240) -> void:
	for _frame in range(max_frames):
		var products: Dictionary = store.product_inventory()
		var total_product: float = 0.0
		for value in products.values():
			total_product += float(value)
		if total_product > 0.0:
			return
		await process_frame
	_assert(false, "Expected product inventory after sandbox UI build/feed sequence")


func _wait_for_tutorial_goal_done(store: Node, goal_id: String, max_frames: int = 240) -> void:
	var expected_line: String = "%s: done" % goal_id
	for _frame in range(max_frames):
		var goals: PackedStringArray = store.tutorial_goal_summary_lines()
		for line in goals:
			if String(line) == expected_line:
				return
		await process_frame
	_assert(false, "Expected tutorial goal '%s' to complete via UI wiring" % goal_id)


func _press_selected_title_button(title_screen: Node, selected_mode: String) -> void:
	var button_path: String = "Center/VBox/SandboxButton"
	if selected_mode == "heater_flash_guided_build_v1":
		button_path = "Center/VBox/TutorialButton"
	var button: Button = title_screen.get_node_or_null(button_path) as Button
	_assert(button != null, "Expected title button at %s" % button_path)
	button.pressed.emit()


func _select_line_endpoint(
	label: Label,
	next_button: Button,
	prefix: String,
	node_id: String,
	max_steps: int = 12
) -> void:
	var expected_text: String = "%s%s" % [prefix, node_id]
	if label.text == expected_text:
		return
	var visited: PackedStringArray = [label.text]
	for _step in range(max_steps):
		next_button.pressed.emit()
		await process_frame
		visited.append(label.text)
		if label.text == expected_text:
			return
	_assert(false,
		"Could not select endpoint '%s'. Visited labels: %s" % [node_id, ", ".join(visited)])


## ── main flow ─────────────────────────────────────────────────────────────────

func _run() -> void:
	## ── PHASE 1: Bootstrap wiring ─────────────────────────────────────────────
	## Bootstrap.tscn root node is named "Bootstrap", so it lands at
	## /root/Bootstrap — matching the NodePaths hard-coded in MainGame.tscn.
	var bootstrap_root: Node = _add_bootstrap_to_root()

	var backend: Node = _get_backend(bootstrap_root)
	_assert(backend != null, "BackendClient node must be present before bootstrap loads")

	var store: Node = _get_store(bootstrap_root)
	_assert(store != null, "SessionStore node must be present before bootstrap loads")

	## BootstrapController._ready() calls configure_from_environment(), then
	## configure_client(), then load_bootstrap().  load_bootstrap() emits
	## bootstrap_updated on success.  Await that signal.
	await _wait_for_bootstrap_loaded(store)

	var modes: Array = store.supported_mode_ids()
	_assert(modes.has("phase1_process_sandbox_v1"),
		"phase1_process_sandbox_v1 must be listed in bootstrap supported_mode_ids")
	_assert(modes.has("heater_flash_guided_build_v1"),
		"heater_flash_guided_build_v1 must be listed in bootstrap supported_mode_ids")

	## After bootstrap BootstrapController calls _show_title_screen(), which
	## instantiates TitleScreen.tscn and adds it to ScreenRoot.
	## One process frame is sufficient for _show_title_screen() to run since
	## it is called synchronously from _ready() after the awaited load_bootstrap.
	var title_screen: Node = await _wait_for_title_screen(bootstrap_root)
	_assert(title_screen != null,
		"TitleScreen must be the active screen inside ScreenRoot after bootstrap")

	var selected_mode: String = _selected_mode_id()
	_assert(
		selected_mode == "phase1_process_sandbox_v1"
			or selected_mode == "heater_flash_guided_build_v1",
		"MODSIM_GODOT_SMOKE_MODE must be phase1_process_sandbox_v1 or heater_flash_guided_build_v1"
	)

	## ── PHASE 2: Selected mode via actual title-screen button path ───────────
	## Drive the real UI button that TitleScreen.tscn wires to the controller.
	_press_selected_title_button(title_screen, selected_mode)

	## Await snapshot_updated.  start_mode() calls apply_authoritative_snapshot()
	## with the initial snapshot from the create-session response, which emits
	## snapshot_updated.
	await _wait_for_snapshot(store)

	_assert(store.active_session_id != "",
		"Session ID must be set on SessionStore after selected mode start")
	_assert(store.active_mode_id == selected_mode,
		"active_mode_id must match the selected mode after start")
	_assert(store.latest_snapshot.has("simulation_snapshot"),
		"latest_snapshot must contain simulation_snapshot key after session creation")

	## ── PHASE 3: MainGame structure and HUD signal-path ──────────────────────
	## _on_mode_selected awaits start_mode() *before* calling _show_main_game(),
	## so MainGame may not yet be in the tree.  Wait until it appears.
	var main_game: Node = await _wait_for_main_game(bootstrap_root)
	_assert(main_game != null,
		"MainGame must be added to ScreenRoot by BootstrapController after mode start")

	## Fixed camera must exist and be the active camera.
	var fixed_camera: Camera3D = main_game.get_node_or_null("World/FixedCamera") as Camera3D
	_assert(fixed_camera != null, "Fixed camera must exist at World/FixedCamera")
	_assert(fixed_camera.current, "Fixed camera must be marked current")

	## Pause button and hotkey must be absent (no pause mechanics in this slice).
	var pause_button: Node = main_game.find_child("PauseButton", true, false)
	_assert(pause_button == null, "Pause button must be omitted from MainGame")
	_assert(not InputMap.has_action("pause"), "Pause hotkey action must not exist")

	## HUD must exist.
	var hud: Node = main_game.get_node_or_null("CanvasLayer/HUD")
	_assert(hud != null, "HudController must exist at CanvasLayer/HUD in MainGame")

	## Prove the signal-path: HUD._ready() connects to SessionStore.snapshot_updated
	## via the NodePath /root/Bootstrap/SessionStore.  The initial snapshot fired
	## before MainGame was added, so the HUD labels are still at defaults ("--").
	## We call store.refresh_snapshot() to emit a new snapshot_updated that the
	## HUD is now subscribed to, then verify the label text was updated by the
	## signal handler (not by a direct call).
	var refresh_ok: bool = await store.refresh_snapshot()
	_assert(refresh_ok, "store.refresh_snapshot() must succeed for signal-path test")
	## Allow one frame for the signal to dispatch through the HUD handler.
	await process_frame

	_assert(hud.cash_label.text.begins_with("Cash:"),
		"HUD cash label must start with 'Cash:' after snapshot_updated signal")
	_assert(not hud.cash_label.text.ends_with("--"),
		"HUD cash label must not be the default '--' after snapshot_updated signal")
	_assert(hud.mode_label.text.contains(selected_mode),
		"HUD mode label must reflect the selected mode_id after snapshot_updated signal")

	## ── PHASE 4: Production BuildCommandPanel command path ───────────────────
	var build_panel: Node = main_game.get_node_or_null("CanvasLayer/HUD/BuildPanel")
	_assert(build_panel != null, "BuildCommandPanel must exist at CanvasLayer/HUD/BuildPanel")

	var build_heater_button: Button = build_panel.get_node_or_null("BuildHeaterButton") as Button
	var build_flash_button: Button = build_panel.get_node_or_null("BuildFlashButton") as Button
	var build_line_button: Button = build_panel.get_node_or_null("BuildLineButton") as Button
	var buy_feed_button: Button = build_panel.get_node_or_null("BuyFeedButton") as Button
	var restart_button: Button = build_panel.get_node_or_null("RestartButton") as Button
	var next_source_button: Button = build_panel.get_node_or_null("LineSourceNextButton") as Button
	var next_target_button: Button = build_panel.get_node_or_null("LineTargetNextButton") as Button
	var source_label: Label = build_panel.get_node_or_null("LineSourceLabel") as Label
	var target_label: Label = build_panel.get_node_or_null("LineTargetLabel") as Label
	var status_label: Label = build_panel.get_node_or_null("StatusLabel") as Label

	_assert(build_heater_button != null, "BuildHeaterButton must exist")
	_assert(build_flash_button != null, "BuildFlashButton must exist")
	_assert(build_line_button != null, "BuildLineButton must exist")
	_assert(buy_feed_button != null, "BuyFeedButton must exist")
	_assert(restart_button != null, "RestartButton must exist")
	_assert(next_source_button != null, "LineSourceNextButton must exist")
	_assert(next_target_button != null, "LineTargetNextButton must exist")
	_assert(source_label != null, "LineSourceLabel must exist")
	_assert(target_label != null, "LineTargetLabel must exist")
	_assert(status_label != null, "StatusLabel must exist")

	var buy_feed_succeeded: bool = false
	buy_feed_button.pressed.emit()
	for _frame in range(120):
		if status_label.text.contains("Bought"):
			buy_feed_succeeded = true
			break
		if status_label.text.contains("Buy feed failed"):
			break
		await process_frame
	if selected_mode == "phase1_process_sandbox_v1":
		_assert(buy_feed_succeeded, "Sandbox mode must support buy-feed via UI")

	build_heater_button.pressed.emit()
	await _wait_for_status_contains(status_label, "Heater placed")

	build_flash_button.pressed.emit()
	await _wait_for_status_contains(status_label, "Flash placed")

	if selected_mode == "heater_flash_guided_build_v1":
		await _select_line_endpoint(source_label, next_source_button, "Line source: ", "feed")
		await _select_line_endpoint(target_label, next_target_button, "Line target: ", "heater_1")
		build_line_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Line built")

		await _select_line_endpoint(source_label, next_source_button, "Line source: ", "heater_1")
		await _select_line_endpoint(target_label, next_target_button, "Line target: ", "flash_1")
		build_line_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Line built")

		await _select_line_endpoint(source_label, next_source_button, "Line source: ", "flash_1")
		await _select_line_endpoint(target_label, next_target_button, "Line target: ", "vapor_product")
		build_line_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Line built")

		await _select_line_endpoint(source_label, next_source_button, "Line source: ", "flash_1")
		await _select_line_endpoint(target_label, next_target_button, "Line target: ", "liquid_product")
		build_line_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Line built")
	else:
		## sandbox: feed_a -> heater_1, then heater_1 -> product_a
		await _select_line_endpoint(source_label, next_source_button, "Line source: ", "feed_a")
		await _select_line_endpoint(target_label, next_target_button, "Line target: ", "heater_1")
		build_line_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Line built")

		await _select_line_endpoint(source_label, next_source_button, "Line source: ", "heater_1")
		await _select_line_endpoint(target_label, next_target_button, "Line target: ", "product_a")
		build_line_button.pressed.emit()
		await _wait_for_status_contains(status_label, "Line built")

	if selected_mode == "heater_flash_guided_build_v1":
		var refresh_tutorial_ok: bool = await store.refresh_snapshot()
		_assert(refresh_tutorial_ok, "Tutorial mode refresh_snapshot() must succeed after UI wiring")
		await process_frame
		await _wait_for_tutorial_goal_done(store, "goal_wire_flowsheet")
		_assert(
			hud.goals_label.text.contains("goal_wire_flowsheet: done"),
			"HUD goals label must reflect completed tutorial wiring goal"
		)
	elif buy_feed_succeeded:
		await _wait_for_goal_or_product(store, selected_mode)

	var original_session_id: String = store.active_session_id
	restart_button.pressed.emit()
	await _wait_for_status_contains(status_label, "Session restarted")
	_assert(store.active_session_id == original_session_id,
		"Restart via UI must preserve active session id")

	## ── DONE ─────────────────────────────────────────────────────────────────
	store.stop_polling()
	bootstrap_root.queue_free()
	await process_frame
	quit(0)
