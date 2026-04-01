extends Node

const DEFAULT_TIMEOUT_SECONDS := 10.0

signal request_slot_released

var api_base_url: String = "http://127.0.0.1:8000"
var _http: HTTPRequest
var _request_in_flight: bool = false
var request_started_count: int = 0
var request_completed_count: int = 0
var request_wait_count: int = 0
var request_timeout_count: int = 0
var _pending_request_completed: bool = false
var _pending_response: Array = []


func _ready() -> void:
	_http = HTTPRequest.new()
	add_child(_http)


func configure(base_url: String) -> void:
	var cleaned := base_url.strip_edges()
	if cleaned == "":
		return
	api_base_url = cleaned.trim_suffix("/")


func configure_from_environment() -> void:
	configure(OS.get_environment("MODSIM_GAME_API_BASE_URL"))


func get_bootstrap() -> Dictionary:
	var result := await _request_json("/game/bootstrap", HTTPClient.METHOD_GET)
	if not bool(result.get("ok", false)):
		return {"ok": false, "error_code": result.get("error_code", "transport_error"), "message": result.get("message", "bootstrap failed")}
	return {"ok": true, "payload": result.payload}


func create_session(mode_id: String, simulation_dt_s: Variant = null) -> Dictionary:
	var body: Dictionary = {"mode_id": mode_id}
	if simulation_dt_s != null:
		body["simulation_dt_s"] = simulation_dt_s
	var result := await _request_json("/game/sessions", HTTPClient.METHOD_POST, body)
	if not bool(result.get("ok", false)):
		return {"ok": false, "error_code": result.get("error_code", "transport_error"), "message": result.get("message", "create-session failed")}
	return {"ok": true, "payload": result.payload}


func get_snapshot(session_id: String) -> Dictionary:
	var result := await _request_json("/game/sessions/%s/snapshot" % session_id, HTTPClient.METHOD_GET)
	if not bool(result.get("ok", false)):
		return {"ok": false, "error_code": result.get("error_code", "transport_error"), "message": result.get("message", "snapshot failed")}
	return {"ok": true, "payload": result.payload}


func build(session_id: String, item_id: String, config: Dictionary = {}, layout: Dictionary = {}) -> Dictionary:
	var payload: Dictionary = {"item_id": item_id, "config": config, "layout": layout}
	var result := await _request_json(
		"/game/sessions/%s/commands/build" % session_id,
		HTTPClient.METHOD_POST,
		payload
	)
	if not bool(result.get("ok", false)):
		return {"ok": false, "error_code": result.get("error_code", "transport_error"), "message": result.get("message", "build failed")}
	return {"ok": true, "payload": result.payload}


func buy_feed(session_id: String, material_id: String, quantity_mol: float) -> Dictionary:
	var result := await _request_json(
		"/game/sessions/%s/commands/buy-feed" % session_id,
		HTTPClient.METHOD_POST,
		{"material_id": material_id, "quantity_mol": quantity_mol}
	)
	if not bool(result.get("ok", false)):
		return {"ok": false, "error_code": result.get("error_code", "transport_error"), "message": result.get("message", "buy-feed failed")}
	return {"ok": true, "payload": result.payload}


func sell_product(session_id: String, product_id: String, quantity_mol: float) -> Dictionary:
	var result := await _request_json(
		"/game/sessions/%s/commands/sell-product" % session_id,
		HTTPClient.METHOD_POST,
		{"product_id": product_id, "quantity_mol": quantity_mol}
	)
	if not bool(result.get("ok", false)):
		return {"ok": false, "error_code": result.get("error_code", "transport_error"), "message": result.get("message", "sell-product failed")}
	return {"ok": true, "payload": result.payload}


func submit_research(session_id: String, research_id: String, submitted_quantities_by_product_id: Dictionary) -> Dictionary:
	var result := await _request_json(
		"/game/sessions/%s/commands/submit-research" % session_id,
		HTTPClient.METHOD_POST,
		{
			"research_id": research_id,
			"submitted_quantities_by_product_id": submitted_quantities_by_product_id,
		}
	)
	if not bool(result.get("ok", false)):
		return {"ok": false, "error_code": result.get("error_code", "transport_error"), "message": result.get("message", "submit-research failed")}
	return {"ok": true, "payload": result.payload}


func restart(session_id: String) -> Dictionary:
	var result := await _request_json(
		"/game/sessions/%s/restart" % session_id,
		HTTPClient.METHOD_POST
	)
	if not bool(result.get("ok", false)):
		return {"ok": false, "error_code": result.get("error_code", "transport_error"), "message": result.get("message", "restart failed")}
	return {"ok": true, "payload": result.payload}


func is_request_in_flight() -> bool:
	return _request_in_flight


func _request_json(path: String, method: int, body: Dictionary = {}) -> Dictionary:
	if _http == null:
		_http = HTTPRequest.new()
		add_child(_http)

	while _request_in_flight:
		request_wait_count += 1
		await request_slot_released
	_request_in_flight = true
	request_started_count += 1

	var body_text := ""
	var headers: PackedStringArray = ["Accept: application/json"]
	if method != HTTPClient.METHOD_GET:
		headers.append("Content-Type: application/json")
		body_text = JSON.stringify(body)

	_pending_request_completed = false
	_pending_response = []
	_http.request_completed.connect(_capture_request_completed, CONNECT_ONE_SHOT)

	var err := _http.request(api_base_url + path, headers, method, body_text)
	if err != OK:
		if _http.request_completed.is_connected(_capture_request_completed):
			_http.request_completed.disconnect(_capture_request_completed)
		_release_request_slot()
		return {
			"ok": false,
			"error_code": "transport_error",
			"message": "HTTP request failed with code %s" % err,
		}

	var deadline_us: int = Time.get_ticks_usec() + int(DEFAULT_TIMEOUT_SECONDS * 1000000.0)
	while not _pending_request_completed or _pending_response.size() < 4:
		if Time.get_ticks_usec() >= deadline_us:
			if _http.request_completed.is_connected(_capture_request_completed):
				_http.request_completed.disconnect(_capture_request_completed)
			_http.cancel_request()
			request_timeout_count += 1
			_release_request_slot()
			return {
				"ok": false,
				"error_code": "transport_timeout",
				"message": "HTTP request timed out after %.1f seconds" % DEFAULT_TIMEOUT_SECONDS,
			}
		await get_tree().process_frame
	request_completed_count += 1
	var response: Array = _pending_response.duplicate()
	_release_request_slot()
	var response_code: int = int(response[1])
	var response_body: PackedByteArray = response[3]
	var response_text := response_body.get_string_from_utf8()

	var parsed: Variant = {}
	if response_text.strip_edges() != "":
		parsed = JSON.parse_string(response_text)
		if parsed == null:
			parsed = {}

	if response_code >= 200 and response_code < 300:
		if parsed is Dictionary:
			return {"ok": true, "payload": parsed}
		return {"ok": true, "payload": {}}

	if parsed is Dictionary:
		return {
			"ok": false,
			"error_code": parsed.get("error_code", "http_%d" % response_code),
			"message": parsed.get("message", "request failed"),
		}

	return {
		"ok": false,
		"error_code": "http_%d" % response_code,
		"message": "HTTP request failed",
	}


func _release_request_slot() -> void:
	if not _request_in_flight:
		return
	_request_in_flight = false
	request_slot_released.emit()


func _capture_request_completed(result: int, response_code: int, headers_value: PackedStringArray, body_value: PackedByteArray) -> void:
	_pending_request_completed = true
	_pending_response = [result, response_code, headers_value, body_value]
