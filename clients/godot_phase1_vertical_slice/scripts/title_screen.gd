extends Control

signal mode_selected(mode_id: String)


func _on_sandbox_pressed() -> void:
	mode_selected.emit("phase1_process_sandbox_v1")


func _on_tutorial_pressed() -> void:
	mode_selected.emit("heater_flash_guided_build_v1")
