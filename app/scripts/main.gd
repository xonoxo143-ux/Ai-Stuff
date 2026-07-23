extends Control

const CATALOG_PATH := "res://data/models.json"
const CHAT_PATH := "user://active_chat.json"

var bridge: Object
var models: Array = []
var history: Array = []
var selected_model: Dictionary = {}
var loaded_filename := ""
var generating := false
var assistant_buffer := ""

var status_label: Label
var model_select: OptionButton
var model_description: Label
var download_button: Button
var load_button: Button
var delete_button: Button
var progress_bar: ProgressBar
var chat_view: RichTextLabel
var prompt_input: TextEdit
var send_button: Button
var stop_button: Button
var system_prompt: TextEdit
var context_spin: SpinBox
var threads_spin: SpinBox
var max_tokens_spin: SpinBox
var temperature_spin: SpinBox
var top_p_spin: SpinBox
var top_k_spin: SpinBox
var repeat_penalty_spin: SpinBox
var stats_label: Label

func _ready() -> void:
	_build_ui()
	_load_catalog()
	_load_chat()
	_connect_bridge()
	_refresh_models()
	_render_chat()

func _build_ui() -> void:
	var background := ColorRect.new()
	background.color = Color("151923")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)

	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 24)
	margin.add_theme_constant_override("margin_right", 24)
	margin.add_theme_constant_override("margin_top", 20)
	margin.add_theme_constant_override("margin_bottom", 20)
	add_child(margin)

	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 12)
	margin.add_child(root)

	var title := Label.new()
	title.text = "Local AI Workbench"
	title.add_theme_font_size_override("font_size", 30)
	root.add_child(title)

	status_label = Label.new()
	status_label.text = "Starting…"
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(status_label)

	var model_row := HBoxContainer.new()
	model_row.add_theme_constant_override("separation", 8)
	root.add_child(model_row)

	model_select = OptionButton.new()
	model_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	model_select.item_selected.connect(_on_model_selected)
	model_row.add_child(model_select)

	download_button = Button.new()
	download_button.text = "Download"
	download_button.pressed.connect(_on_download_pressed)
	model_row.add_child(download_button)

	load_button = Button.new()
	load_button.text = "Load"
	load_button.pressed.connect(_on_load_pressed)
	model_row.add_child(load_button)

	delete_button = Button.new()
	delete_button.text = "Delete"
	delete_button.pressed.connect(_on_delete_pressed)
	model_row.add_child(delete_button)

	model_description = Label.new()
	model_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(model_description)

	progress_bar = ProgressBar.new()
	progress_bar.min_value = 0
	progress_bar.max_value = 100
	progress_bar.value = 0
	progress_bar.show_percentage = true
	root.add_child(progress_bar)

	var settings_title := Label.new()
	settings_title.text = "Model and sampling settings"
	settings_title.add_theme_font_size_override("font_size", 20)
	root.add_child(settings_title)

	var settings_grid := GridContainer.new()
	settings_grid.columns = 4
	settings_grid.add_theme_constant_override("h_separation", 8)
	settings_grid.add_theme_constant_override("v_separation", 6)
	root.add_child(settings_grid)

	context_spin = _add_spin(settings_grid, "Context", 512, 32768, 512, 4096)
	threads_spin = _add_spin(settings_grid, "Threads", 1, 12, 1, 4)
	max_tokens_spin = _add_spin(settings_grid, "Max tokens", 16, 4096, 16, 512)
	temperature_spin = _add_spin(settings_grid, "Temperature", 0, 2, 0.05, 0.7)
	top_p_spin = _add_spin(settings_grid, "Top-p", 0.05, 1, 0.05, 0.95)
	top_k_spin = _add_spin(settings_grid, "Top-k", 0, 200, 1, 40)
	repeat_penalty_spin = _add_spin(settings_grid, "Repeat penalty", 1, 2, 0.05, 1.1)

	var system_label := Label.new()
	system_label.text = "System prompt"
	root.add_child(system_label)

	system_prompt = TextEdit.new()
	system_prompt.custom_minimum_size.y = 86
	system_prompt.text = "You are a useful local assistant. Be accurate, direct, and concise."
	root.add_child(system_prompt)

	chat_view = RichTextLabel.new()
	chat_view.bbcode_enabled = true
	chat_view.fit_content = false
	chat_view.scroll_active = true
	chat_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	chat_view.custom_minimum_size.y = 400
	root.add_child(chat_view)

	prompt_input = TextEdit.new()
	prompt_input.custom_minimum_size.y = 110
	prompt_input.placeholder_text = "Type a message…"
	root.add_child(prompt_input)

	var action_row := HBoxContainer.new()
	action_row.add_theme_constant_override("separation", 8)
	root.add_child(action_row)

	send_button = Button.new()
	send_button.text = "Send"
	send_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	send_button.pressed.connect(_on_send_pressed)
	action_row.add_child(send_button)

	stop_button = Button.new()
	stop_button.text = "Stop"
	stop_button.disabled = true
	stop_button.pressed.connect(_on_stop_pressed)
	action_row.add_child(stop_button)

	var clear_button := Button.new()
	clear_button.text = "Clear chat"
	clear_button.pressed.connect(_on_clear_pressed)
	action_row.add_child(clear_button)

	stats_label = Label.new()
	stats_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(stats_label)

func _add_spin(parent: GridContainer, label_text: String, min_value: float, max_value: float, step: float, value: float) -> SpinBox:
	var label := Label.new()
	label.text = label_text
	parent.add_child(label)
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = step
	spin.value = value
	spin.allow_greater = false
	spin.allow_lesser = false
	spin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(spin)
	return spin

func _load_catalog() -> void:
	var file := FileAccess.open(CATALOG_PATH, FileAccess.READ)
	if file == null:
		_set_status("Catalogue could not be opened.")
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("models"):
		_set_status("Catalogue JSON is invalid.")
		return
	models = parsed["models"]
	model_select.clear()
	for model in models:
		model_select.add_item(str(model.get("name", model.get("id", "Model"))))
	if not models.is_empty():
		_select_model(0)

func _connect_bridge() -> void:
	if not Engine.has_singleton("LocalAI"):
		_set_status("Android inference plugin is unavailable in the editor. Install the APK or compiled AAR.")
		return
	bridge = Engine.get_singleton("LocalAI")
	for pair in [
		["download_progress", _on_download_progress],
		["download_finished", _on_download_finished],
		["download_failed", _on_download_failed],
		["models_changed", _on_models_changed],
		["model_loaded", _on_model_loaded],
		["model_unloaded", _on_model_unloaded],
		["token_received", _on_token_received],
		["generation_finished", _on_generation_finished],
		["ai_error", _on_ai_error]
	]:
		if bridge.has_signal(pair[0]) and not bridge.is_connected(pair[0], pair[1]):
			bridge.connect(pair[0], pair[1])
	_set_status("Ready. Choose a model to download or load.")
	var info := str(bridge.systemInfo())
	if not info.is_empty():
		stats_label.text = info

func _on_model_selected(index: int) -> void:
	_select_model(index)

func _select_model(index: int) -> void:
	if index < 0 or index >= models.size():
		return
	selected_model = models[index]
	model_description.text = "%s\nSource: %s\nFile: %s" % [
		selected_model.get("description", ""),
		selected_model.get("source", ""),
		selected_model.get("filename", "")
	]
	var recommended: Dictionary = selected_model.get("recommended", {})
	context_spin.value = float(recommended.get("context", 4096))
	threads_spin.value = float(recommended.get("threads", 4))
	max_tokens_spin.value = float(recommended.get("max_tokens", 512))
	_refresh_models()

func _refresh_models() -> void:
	if bridge == null or selected_model.is_empty():
		download_button.disabled = true
		load_button.disabled = true
		delete_button.disabled = true
		return
	var path := str(bridge.getModelPath(str(selected_model["filename"])))
	var installed := not path.is_empty()
	download_button.disabled = installed
	load_button.disabled = not installed or generating
	delete_button.disabled = not installed or generating
	if installed:
		_set_status("Installed: " + path)
	else:
		_set_status("Model is not downloaded.")

func _on_download_pressed() -> void:
	if bridge == null or selected_model.is_empty():
		return
	progress_bar.value = 0
	download_button.disabled = true
	_set_status("Starting download…")
	bridge.downloadModel(
		str(selected_model["id"]),
		str(selected_model["url"]),
		str(selected_model["filename"]),
		str(selected_model.get("sha256", ""))
	)

func _on_load_pressed() -> void:
	if bridge == null or selected_model.is_empty():
		return
	var path := str(bridge.getModelPath(str(selected_model["filename"])))
	if path.is_empty():
		_set_status("Download the model first.")
		return
	load_button.disabled = true
	_set_status("Loading model…")
	bridge.loadModel(path, int(context_spin.value), int(threads_spin.value), 0)

func _on_delete_pressed() -> void:
	if bridge == null or selected_model.is_empty():
		return
	if loaded_filename == str(selected_model["filename"]):
		bridge.unloadModel()
	bridge.deleteModel(str(selected_model["filename"]))
	loaded_filename = ""
	_refresh_models()

func _on_send_pressed() -> void:
	if bridge == null:
		_set_status("The Android inference plugin is not available.")
		return
	if loaded_filename.is_empty():
		_set_status("Load a model before sending.")
		return
	var text := prompt_input.text.strip_edges()
	if text.is_empty() or generating:
		return
	history.append({"role": "user", "content": text})
	prompt_input.clear()
	assistant_buffer = ""
	generating = true
	send_button.disabled = true
	stop_button.disabled = false
	load_button.disabled = true
	delete_button.disabled = true
	_render_chat(true)
	_save_chat()
	var prompt := _build_prompt()
	bridge.generate(
		prompt,
		int(max_tokens_spin.value),
		float(temperature_spin.value),
		float(top_p_spin.value),
		int(top_k_spin.value),
		float(repeat_penalty_spin.value)
	)

func _build_prompt() -> String:
	var result := ""
	var template := str(selected_model.get("template", "chatml"))
	if template == "chatml":
		result += "<|im_start|>system\n%s<|im_end|>\n" % system_prompt.text.strip_edges()
		for message in history:
			result += "<|im_start|>%s\n%s<|im_end|>\n" % [message["role"], message["content"]]
		result += "<|im_start|>assistant\n"
		return result
	result += system_prompt.text.strip_edges() + "\n\n"
	for message in history:
		result += "%s: %s\n" % [str(message["role"]).capitalize(), message["content"]]
	return result + "Assistant: "

func _on_stop_pressed() -> void:
	if bridge != null:
		bridge.stopGeneration()
	_set_status("Stopping after the current token…")

func _on_clear_pressed() -> void:
	if generating:
		return
	history.clear()
	assistant_buffer = ""
	_save_chat()
	_render_chat()
	_set_status("Conversation cleared.")

func _on_download_progress(payload: String) -> void:
	var data := _json_dict(payload)
	progress_bar.value = float(data.get("percent", 0))
	_set_status("Downloading %s — %.1f%%" % [data.get("filename", "model"), progress_bar.value])

func _on_download_finished(payload: String) -> void:
	var data := _json_dict(payload)
	progress_bar.value = 100
	_set_status("Download verified: " + str(data.get("path", "")))
	_refresh_models()

func _on_download_failed(payload: String) -> void:
	var data := _json_dict(payload)
	_set_status("Download failed: " + str(data.get("message", payload)))
	_refresh_models()

func _on_models_changed(_payload: String) -> void:
	_refresh_models()

func _on_model_loaded(payload: String) -> void:
	var data := _json_dict(payload)
	loaded_filename = str(data.get("filename", selected_model.get("filename", "")))
	_set_status("Model loaded: " + loaded_filename)
	stats_label.text = "Backend: %s | Context: %s | Threads: %s" % [
		data.get("backend", "CPU"),
		data.get("context", "?"),
		data.get("threads", "?")
	]
	_refresh_models()

func _on_model_unloaded(_payload: String) -> void:
	loaded_filename = ""
	_set_status("Model unloaded.")
	_refresh_models()

func _on_token_received(token: String) -> void:
	assistant_buffer += token
	_render_chat(true)

func _on_generation_finished(payload: String) -> void:
	var data := _json_dict(payload)
	if not assistant_buffer.is_empty():
		history.append({"role": "assistant", "content": assistant_buffer})
	assistant_buffer = ""
	generating = false
	send_button.disabled = false
	stop_button.disabled = true
	stats_label.text = "Generated %s tokens in %.2f s — %.2f tokens/s" % [
		data.get("tokens", 0),
		float(data.get("seconds", 0)),
		float(data.get("tokens_per_second", 0))
	]
	_set_status("Generation complete.")
	_save_chat()
	_render_chat()
	_refresh_models()

func _on_ai_error(payload: String) -> void:
	var data := _json_dict(payload)
	generating = false
	send_button.disabled = false
	stop_button.disabled = true
	_set_status("AI error: " + str(data.get("message", payload)))
	_refresh_models()

func _render_chat(include_stream: bool = false) -> void:
	if chat_view == null:
		return
	chat_view.clear()
	for message in history:
		var role := "You" if message["role"] == "user" else "Assistant"
		chat_view.append_text("[b]%s[/b]\n%s\n\n" % [role, _escape_bbcode(str(message["content"]))])
	if include_stream:
		chat_view.append_text("[b]Assistant[/b]\n%s" % _escape_bbcode(assistant_buffer))
	await get_tree().process_frame
	chat_view.scroll_to_line(max(0, chat_view.get_line_count() - 1))

func _escape_bbcode(value: String) -> String:
	return value.replace("[", "[lb]")

func _set_status(text: String) -> void:
	if status_label != null:
		status_label.text = text

func _json_dict(payload: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(payload)
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}

func _save_chat() -> void:
	var file := FileAccess.open(CHAT_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify({"history": history, "system_prompt": system_prompt.text}))

func _load_chat() -> void:
	var file := FileAccess.open(CHAT_PATH, FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) == TYPE_DICTIONARY:
		history = parsed.get("history", [])
		if system_prompt != null:
			system_prompt.text = str(parsed.get("system_prompt", system_prompt.text))
