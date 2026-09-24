extends Control

const WorkspaceStore = preload("res://scripts/workspace_store.gd")
const GitHubSync = preload("res://scripts/github_sync.gd")

const CATALOG_PATH := "res://data/models.json"
const CHAT_PATH := "user://active_chat.json"

var bridge: Object
var store: RefCounted
var github_sync: Node

var models: Array = []
var history: Array = []
var selected_model: Dictionary = {}
var loaded_filename := ""
var generating := false
var assistant_buffer := ""
var generation_mode := "chat"
var last_chat_exchange: Dictionary = {}

var benchmark_suite: Dictionary = {}
var benchmark_turns: Array = []
var benchmark_threads: Dictionary = {}
var benchmark_results: Array = []
var benchmark_index := 0
var benchmark_active := false
var benchmark_cancel_requested := false
var current_benchmark_turn: Dictionary = {}

var global_status: Label
var sync_status: Label
var pull_button: Button
var push_button: Button

var model_select: OptionButton
var model_description: Label
var download_button: Button
var load_button: Button
var unload_button: Button
var delete_button: Button
var progress_bar: ProgressBar
var run_stats: Label

var chat_view: RichTextLabel
var prompt_input: TextEdit
var send_button: Button
var stop_button: Button
var system_prompt: TextEdit
var good_button: Button
var poor_button: Button

var context_spin: SpinBox
var threads_spin: SpinBox
var max_tokens_spin: SpinBox
var temperature_spin: SpinBox
var top_p_spin: SpinBox
var top_k_spin: SpinBox
var repeat_penalty_spin: SpinBox

var benchmark_select: OptionButton
var benchmark_run_button: Button
var benchmark_stop_button: Button
var benchmark_progress: ProgressBar
var benchmark_status: Label
var benchmark_preview: RichTextLabel

var data_status: Label
var token_status: Label
var token_dialog: AcceptDialog
var token_input: LineEdit

func _ready() -> void:
	store = WorkspaceStore.new()
	store.initialize()
	_build_ui()
	_load_catalog()
	_load_chat()
	_connect_bridge()
	github_sync = GitHubSync.new()
	add_child(github_sync)
	github_sync.configure(store)
	_refresh_benchmarks()
	_refresh_models()
	_render_chat()
	_refresh_workspace_status()

func _build_ui() -> void:
	var background := ColorRect.new()
	background.color = Color("151923")
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(background)

	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 20)
	margin.add_theme_constant_override("margin_right", 20)
	margin.add_theme_constant_override("margin_top", 16)
	margin.add_theme_constant_override("margin_bottom", 16)
	add_child(margin)

	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 10)
	margin.add_child(root)

	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 8)
	root.add_child(header)

	var title := Label.new()
	title.text = "AI Workbench"
	title.add_theme_font_size_override("font_size", 28)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)

	pull_button = Button.new()
	pull_button.text = "↓ Pull"
	pull_button.pressed.connect(_on_pull_pressed)
	header.add_child(pull_button)

	push_button = Button.new()
	push_button.text = "↑ Push"
	push_button.pressed.connect(_on_push_pressed)
	header.add_child(push_button)

	sync_status = Label.new()
	sync_status.text = "Workspace local"
	sync_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(sync_status)

	global_status = Label.new()
	global_status.text = "Starting…"
	global_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(global_status)

	var tabs := TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(tabs)

	var run_page := _new_page("Run")
	tabs.add_child(run_page)
	_build_run_tab(run_page)

	var chat_page := _new_page("Chat")
	tabs.add_child(chat_page)
	_build_chat_tab(chat_page)

	var bench_page := _new_page("Bench")
	tabs.add_child(bench_page)
	_build_bench_tab(bench_page)

	var data_page := _new_page("Data")
	tabs.add_child(data_page)
	_build_data_tab(data_page)

	_build_token_dialog()

func _new_page(name_value: String) -> ScrollContainer:
	var scroll := ScrollContainer.new()
	scroll.name = name_value
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	var body := VBoxContainer.new()
	body.name = "Body"
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 10)
	scroll.add_child(body)
	return scroll

func _page_body(page: ScrollContainer) -> VBoxContainer:
	return page.get_node("Body") as VBoxContainer

func _build_run_tab(page: ScrollContainer) -> void:
	var body := _page_body(page)

	var model_title := Label.new()
	model_title.text = "Local model"
	model_title.add_theme_font_size_override("font_size", 20)
	body.add_child(model_title)

	var model_row := HBoxContainer.new()
	model_row.add_theme_constant_override("separation", 6)
	body.add_child(model_row)

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

	unload_button = Button.new()
	unload_button.text = "Unload"
	unload_button.pressed.connect(_on_unload_pressed)
	model_row.add_child(unload_button)

	delete_button = Button.new()
	delete_button.text = "Delete"
	delete_button.pressed.connect(_on_delete_pressed)
	model_row.add_child(delete_button)

	model_description = Label.new()
	model_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(model_description)

	progress_bar = ProgressBar.new()
	progress_bar.min_value = 0
	progress_bar.max_value = 100
	progress_bar.value = 0
	progress_bar.show_percentage = true
	body.add_child(progress_bar)

	var settings_title := Label.new()
	settings_title.text = "Runtime"
	settings_title.add_theme_font_size_override("font_size", 20)
	body.add_child(settings_title)

	var settings_grid := GridContainer.new()
	settings_grid.columns = 4
	settings_grid.add_theme_constant_override("h_separation", 8)
	settings_grid.add_theme_constant_override("v_separation", 6)
	body.add_child(settings_grid)

	context_spin = _add_spin(settings_grid, "Context", 512, 32768, 512, 4096)
	threads_spin = _add_spin(settings_grid, "Threads", 1, 16, 1, 4)
	max_tokens_spin = _add_spin(settings_grid, "Max tokens", 16, 4096, 16, 512)
	temperature_spin = _add_spin(settings_grid, "Temperature", 0.01, 2, 0.05, 0.7)
	top_p_spin = _add_spin(settings_grid, "Top-p", 0.05, 1, 0.05, 0.95)
	top_k_spin = _add_spin(settings_grid, "Top-k", 0, 200, 1, 40)
	repeat_penalty_spin = _add_spin(settings_grid, "Repeat penalty", 1, 2, 0.05, 1.1)

	run_stats = Label.new()
	run_stats.text = "No model loaded."
	run_stats.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(run_stats)

func _build_chat_tab(page: ScrollContainer) -> void:
	var body := _page_body(page)

	var system_label := Label.new()
	system_label.text = "System prompt"
	body.add_child(system_label)

	system_prompt = TextEdit.new()
	system_prompt.custom_minimum_size.y = 82
	system_prompt.text = "You are a useful local assistant. Be accurate, direct, and concise."
	body.add_child(system_prompt)

	chat_view = RichTextLabel.new()
	chat_view.bbcode_enabled = true
	chat_view.fit_content = false
	chat_view.scroll_active = true
	chat_view.custom_minimum_size.y = 520
	body.add_child(chat_view)

	prompt_input = TextEdit.new()
	prompt_input.custom_minimum_size.y = 105
	prompt_input.placeholder_text = "Type a message…"
	body.add_child(prompt_input)

	var action_row := HBoxContainer.new()
	action_row.add_theme_constant_override("separation", 6)
	body.add_child(action_row)

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
	clear_button.text = "Clear"
	clear_button.pressed.connect(_on_clear_pressed)
	action_row.add_child(clear_button)

	var rating_row := HBoxContainer.new()
	rating_row.add_theme_constant_override("separation", 6)
	body.add_child(rating_row)

	var rating_label := Label.new()
	rating_label.text = "Save last response:"
	rating_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rating_row.add_child(rating_label)

	good_button = Button.new()
	good_button.text = "Useful"
	good_button.disabled = true
	good_button.pressed.connect(func(): _queue_chat_rating("useful"))
	rating_row.add_child(good_button)

	poor_button = Button.new()
	poor_button.text = "Poor"
	poor_button.disabled = true
	poor_button.pressed.connect(func(): _queue_chat_rating("poor"))
	rating_row.add_child(poor_button)

func _build_bench_tab(page: ScrollContainer) -> void:
	var body := _page_body(page)

	var title := Label.new()
	title.text = "Benchmark"
	title.add_theme_font_size_override("font_size", 20)
	body.add_child(title)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	body.add_child(row)

	benchmark_select = OptionButton.new()
	benchmark_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(benchmark_select)

	benchmark_run_button = Button.new()
	benchmark_run_button.text = "Run"
	benchmark_run_button.pressed.connect(_on_run_benchmark_pressed)
	row.add_child(benchmark_run_button)

	benchmark_stop_button = Button.new()
	benchmark_stop_button.text = "Stop"
	benchmark_stop_button.disabled = true
	benchmark_stop_button.pressed.connect(_on_stop_benchmark_pressed)
	row.add_child(benchmark_stop_button)

	benchmark_progress = ProgressBar.new()
	benchmark_progress.min_value = 0
	benchmark_progress.max_value = 1
	benchmark_progress.value = 0
	benchmark_progress.show_percentage = true
	body.add_child(benchmark_progress)

	benchmark_status = Label.new()
	benchmark_status.text = "Pull a workspace or use the bundled benchmark."
	benchmark_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(benchmark_status)

	benchmark_preview = RichTextLabel.new()
	benchmark_preview.bbcode_enabled = true
	benchmark_preview.custom_minimum_size.y = 420
	body.add_child(benchmark_preview)

func _build_data_tab(page: ScrollContainer) -> void:
	var body := _page_body(page)

	var title := Label.new()
	title.text = "Data / workspace"
	title.add_theme_font_size_override("font_size", 20)
	body.add_child(title)

	var explanation := Label.new()
	explanation.text = "Large models and datasets stay on-device. GitHub carries manifests, experiment definitions, small logs, and selected results."
	explanation.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(explanation)

	token_status = Label.new()
	token_status.text = "GitHub push credential: not checked"
	body.add_child(token_status)

	var token_button := Button.new()
	token_button.text = "Configure GitHub token"
	token_button.pressed.connect(_on_configure_token_pressed)
	body.add_child(token_button)

	data_status = Label.new()
	data_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(data_status)

func _build_token_dialog() -> void:
	token_dialog = AcceptDialog.new()
	token_dialog.title = "GitHub push credential"
	token_dialog.dialog_text = "Paste a fine-grained GitHub token with Contents write access to Ai-Stuff. It is encrypted with Android Keystore and never committed."
	token_dialog.confirmed.connect(_on_token_confirmed)
	add_child(token_dialog)

	token_input = LineEdit.new()
	token_input.secret = true
	token_input.placeholder_text = "github_pat_…"
	token_input.custom_minimum_size.x = 650
	token_dialog.add_child(token_input)

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
		_set_status("Model catalogue could not be opened.")
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("models"):
		_set_status("Model catalogue JSON is invalid.")
		return
	models = parsed["models"]
	model_select.clear()
	for model in models:
		model_select.add_item(str(model.get("name", model.get("id", "Model"))))
	if not models.is_empty():
		_select_model(0)

func _connect_bridge() -> void:
	if not Engine.has_singleton("LocalAI"):
		_set_status("Android inference plugin unavailable here. UI/workspace logic can still be exercised.")
		run_stats.text = "Native llama.cpp backend not present in this runtime."
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
	_set_status("Ready.")
	var info := str(bridge.systemInfo())
	if not info.is_empty():
		run_stats.text = info

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

func _on_model_selected(index: int) -> void:
	_select_model(index)

func _refresh_models() -> void:
	if bridge == null or selected_model.is_empty():
		download_button.disabled = true
		load_button.disabled = true
		unload_button.disabled = true
		delete_button.disabled = true
		send_button.disabled = true
		benchmark_run_button.disabled = true
		return
	var path := str(bridge.getModelPath(str(selected_model["filename"])))
	var installed := not path.is_empty()
	var selected_is_loaded := loaded_filename == str(selected_model.get("filename", ""))
	download_button.disabled = installed
	load_button.disabled = not installed or generating or selected_is_loaded
	unload_button.disabled = loaded_filename.is_empty() or generating
	delete_button.disabled = not installed or generating
	send_button.disabled = loaded_filename.is_empty() or generating
	benchmark_run_button.disabled = loaded_filename.is_empty() or generating or benchmark_active

func _on_download_pressed() -> void:
	if bridge == null or selected_model.is_empty():
		return
	progress_bar.value = 0
	download_button.disabled = true
	_set_status("Starting model download…")
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

func _on_unload_pressed() -> void:
	if bridge == null or loaded_filename.is_empty() or generating:
		return
	_set_status("Unloading model…")
	bridge.unloadModel()

func _on_delete_pressed() -> void:
	if bridge == null or selected_model.is_empty() or generating:
		return
	if loaded_filename == str(selected_model["filename"]):
		bridge.unloadModel()
	bridge.deleteModel(str(selected_model["filename"]))
	loaded_filename = ""
	_refresh_models()

func _on_send_pressed() -> void:
	if bridge == null:
		_set_status("Native inference is unavailable.")
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
	generation_mode = "chat"
	generating = true
	last_chat_exchange = {}
	good_button.disabled = true
	poor_button.disabled = true
	_set_generation_controls(true)
	_render_chat(true)
	_save_chat()
	bridge.generate(
		_build_prompt_for(history, system_prompt.text),
		int(max_tokens_spin.value),
		float(temperature_spin.value),
		float(top_p_spin.value),
		int(top_k_spin.value),
		float(repeat_penalty_spin.value)
	)

func _on_stop_pressed() -> void:
	if bridge != null:
		bridge.stopGeneration()
	_set_status("Stopping after the current token…")

func _on_clear_pressed() -> void:
	if generating:
		return
	history.clear()
	assistant_buffer = ""
	last_chat_exchange = {}
	good_button.disabled = true
	poor_button.disabled = true
	_save_chat()
	_render_chat()
	_set_status("Conversation cleared.")

func _on_run_benchmark_pressed() -> void:
	if bridge == null or loaded_filename.is_empty() or benchmark_active:
		return
	if benchmark_select.item_count == 0:
		benchmark_status.text = "No benchmark suite is available."
		return
	var filename := benchmark_select.get_item_metadata(benchmark_select.selected)
	if filename == null:
		filename = benchmark_select.get_item_text(benchmark_select.selected)
	var parsed: Variant = store.read_json(store.benchmark_path(str(filename)))
	if typeof(parsed) != TYPE_DICTIONARY or typeof(parsed.get("turns", null)) != TYPE_ARRAY:
		benchmark_status.text = "Benchmark JSON is invalid."
		return
	benchmark_suite = parsed
	benchmark_turns = benchmark_suite.get("turns", [])
	benchmark_threads.clear()
	benchmark_results.clear()
	benchmark_index = 0
	benchmark_active = true
	benchmark_cancel_requested = false
	benchmark_progress.max_value = max(1, benchmark_turns.size())
	benchmark_progress.value = 0
	benchmark_run_button.disabled = true
	benchmark_stop_button.disabled = false
	benchmark_status.text = "Running %s…" % str(benchmark_suite.get("id", filename))
	benchmark_preview.clear()
	_run_next_benchmark_turn()

func _run_next_benchmark_turn() -> void:
	if not benchmark_active:
		return
	if benchmark_cancel_requested or benchmark_index >= benchmark_turns.size():
		_finish_benchmark(not benchmark_cancel_requested)
		return
	current_benchmark_turn = benchmark_turns[benchmark_index]
	var thread_id := str(current_benchmark_turn.get("thread", "default"))
	var thread_history: Array = benchmark_threads.get(thread_id, []).duplicate(true)
	thread_history.append({
		"role": "user",
		"content": str(current_benchmark_turn.get("prompt", ""))
	})
	benchmark_threads[thread_id] = thread_history
	assistant_buffer = ""
	generation_mode = "benchmark"
	generating = true
	_set_generation_controls(true)
	benchmark_status.text = "Turn %d/%d — %s" % [
		benchmark_index + 1,
		benchmark_turns.size(),
		str(current_benchmark_turn.get("category", "task"))
	]
	benchmark_preview.clear()
	benchmark_preview.append_text("[b]Prompt[/b]\n%s\n\n[b]Response[/b]\n" % _escape_bbcode(str(current_benchmark_turn.get("prompt", ""))))
	var bench_system := str(benchmark_suite.get("system_prompt", "You are a capable local assistant. Follow the user request accurately."))
	bridge.generate(
		_build_prompt_for(thread_history, bench_system),
		int(max_tokens_spin.value),
		float(temperature_spin.value),
		float(top_p_spin.value),
		int(top_k_spin.value),
		float(repeat_penalty_spin.value)
	)

func _on_stop_benchmark_pressed() -> void:
	if not benchmark_active:
		return
	benchmark_cancel_requested = true
	if bridge != null and generating:
		bridge.stopGeneration()
	benchmark_status.text = "Stopping benchmark…"

func _on_token_received(token: String) -> void:
	assistant_buffer += token
	if generation_mode == "benchmark":
		benchmark_preview.clear()
		benchmark_preview.append_text("[b]Prompt[/b]\n%s\n\n[b]Response[/b]\n%s" % [
			_escape_bbcode(str(current_benchmark_turn.get("prompt", ""))),
			_escape_bbcode(assistant_buffer)
		])
	else:
		_render_chat(true)

func _on_generation_finished(payload: String) -> void:
	var data := _json_dict(payload)
	generating = false
	_set_generation_controls(false)
	if generation_mode == "benchmark":
		_finish_benchmark_turn(data)
	else:
		_finish_chat_generation(data)
	_refresh_models()

func _finish_chat_generation(metrics: Dictionary) -> void:
	var response := assistant_buffer
	if not response.is_empty():
		history.append({"role": "assistant", "content": response})
	var user_text := ""
	if history.size() >= 2:
		user_text = str(history[history.size() - 2].get("content", ""))
	last_chat_exchange = {
		"prompt": user_text,
		"response": response,
		"metrics": metrics.duplicate(true),
		"model": str(selected_model.get("id", loaded_filename)),
		"timestamp": Time.get_datetime_string_from_system(true)
	}
	assistant_buffer = ""
	good_button.disabled = response.is_empty()
	poor_button.disabled = response.is_empty()
	_set_status("Generation complete.")
	run_stats.text = _format_metrics(metrics)
	_save_chat()
	_render_chat()

func _finish_benchmark_turn(metrics: Dictionary) -> void:
	var response := assistant_buffer
	var thread_id := str(current_benchmark_turn.get("thread", "default"))
	var thread_history: Array = benchmark_threads.get(thread_id, []).duplicate(true)
	thread_history.append({"role": "assistant", "content": response})
	benchmark_threads[thread_id] = thread_history

	var checks := _evaluate_checks(response, current_benchmark_turn.get("checks", []))
	benchmark_results.append({
		"id": str(current_benchmark_turn.get("id", "turn-%d" % benchmark_index)),
		"thread": thread_id,
		"category": str(current_benchmark_turn.get("category", "")),
		"prompt": str(current_benchmark_turn.get("prompt", "")),
		"response": response,
		"criteria": current_benchmark_turn.get("criteria", []),
		"objective_checks": checks,
		"metrics": metrics.duplicate(true)
	})
	assistant_buffer = ""
	benchmark_index += 1
	benchmark_progress.value = benchmark_index
	run_stats.text = _format_metrics(metrics)
	if benchmark_cancel_requested:
		_finish_benchmark(false)
	else:
		call_deferred("_run_next_benchmark_turn")

func _finish_benchmark(complete: bool) -> void:
	benchmark_active = false
	benchmark_run_button.disabled = loaded_filename.is_empty()
	benchmark_stop_button.disabled = true
	generating = false
	_set_generation_controls(false)

	var objective_total := 0
	var objective_passed := 0
	var ttft_sum := 0.0
	var ttft_count := 0
	var rate_sum := 0.0
	var rate_count := 0
	for result in benchmark_results:
		for check in result.get("objective_checks", []):
			objective_total += 1
			if check.get("passed", false):
				objective_passed += 1
		var metrics: Dictionary = result.get("metrics", {})
		if metrics.has("ttft_seconds"):
			ttft_sum += float(metrics.get("ttft_seconds", 0.0))
			ttft_count += 1
		if metrics.has("tokens_per_second"):
			rate_sum += float(metrics.get("tokens_per_second", 0.0))
			rate_count += 1

	var payload := {
		"schema": 1,
		"type": "benchmark_result",
		"suite": str(benchmark_suite.get("id", "unknown")),
		"complete": complete,
		"generated_at": Time.get_datetime_string_from_system(true),
		"device_id": _device_id(),
		"model": {
			"id": str(selected_model.get("id", "")),
			"filename": loaded_filename
		},
		"settings": _generation_settings(),
		"summary": {
			"turns_completed": benchmark_results.size(),
			"turns_total": benchmark_turns.size(),
			"objective_passed": objective_passed,
			"objective_total": objective_total,
			"mean_ttft_seconds": ttft_sum / ttft_count if ttft_count > 0 else null,
			"mean_generation_tokens_per_second": rate_sum / rate_count if rate_count > 0 else null
		},
		"turns": benchmark_results
	}
	var saved := store.queue_result(payload, "benchmark")
	benchmark_status.text = "%s Saved locally and queued for push: %s" % [
		"Complete." if complete else "Stopped.",
		saved
	]
	_refresh_workspace_status()
	_refresh_models()

func _evaluate_checks(response: String, checks_value: Variant) -> Array:
	var results: Array = []
	if typeof(checks_value) != TYPE_ARRAY:
		return results
	for check_value in checks_value:
		if typeof(check_value) != TYPE_DICTIONARY:
			continue
		var check: Dictionary = check_value
		var kind := str(check.get("type", ""))
		var passed := false
		if kind == "regex":
			var regex := RegEx.new()
			if regex.compile(str(check.get("pattern", ""))) == OK:
				passed = regex.search(response) != null
		elif kind == "contains_all":
			passed = true
			var lower := response.to_lower()
			for item in check.get("values", []):
				if not lower.contains(str(item).to_lower()):
					passed = false
					break
		results.append({
			"type": kind,
			"passed": passed,
			"definition": check
		})
	return results

func _queue_chat_rating(rating: String) -> void:
	if last_chat_exchange.is_empty():
		return
	var payload := last_chat_exchange.duplicate(true)
	payload["schema"] = 1
	payload["type"] = "chat_rating"
	payload["rating"] = rating
	payload["device_id"] = _device_id()
	var saved := store.queue_result(payload, "chat")
	good_button.disabled = true
	poor_button.disabled = true
	_set_status("Saved %s rating to outbox: %s" % [rating, saved.get_file()])
	_refresh_workspace_status()

func _build_prompt_for(messages: Array, system_text: String) -> String:
	var result := ""
	var template := str(selected_model.get("template", "chatml"))
	if template == "chatml":
		result += "<|im_start|>system\n%s<|im_end|>\n" % system_text.strip_edges()
		for message in messages:
			result += "<|im_start|>%s\n%s<|im_end|>\n" % [message["role"], message["content"]]
		result += "<|im_start|>assistant\n"
		return result
	result += system_text.strip_edges() + "\n\n"
	for message in messages:
		result += "%s: %s\n" % [str(message["role"]).capitalize(), message["content"]]
	return result + "Assistant: "

func _generation_settings() -> Dictionary:
	return {
		"context": int(context_spin.value),
		"threads": int(threads_spin.value),
		"max_tokens": int(max_tokens_spin.value),
		"temperature": float(temperature_spin.value),
		"top_p": float(top_p_spin.value),
		"top_k": int(top_k_spin.value),
		"repeat_penalty": float(repeat_penalty_spin.value)
	}

func _format_metrics(data: Dictionary) -> String:
	return "Prompt %s tok / %.3fs | TTFT %.3fs | Generated %s tok / %.2f tok/s | Total %.3fs" % [
		data.get("prompt_tokens", "?"),
		float(data.get("prompt_seconds", 0.0)),
		float(data.get("ttft_seconds", 0.0)),
		data.get("tokens", 0),
		float(data.get("tokens_per_second", 0.0)),
		float(data.get("total_seconds", data.get("seconds", 0.0)))
	]

func _set_generation_controls(active: bool) -> void:
	send_button.disabled = active or loaded_filename.is_empty()
	stop_button.disabled = not active
	load_button.disabled = active
	unload_button.disabled = active or loaded_filename.is_empty()
	delete_button.disabled = active
	if benchmark_active:
		benchmark_run_button.disabled = true
	else:
		benchmark_run_button.disabled = active or loaded_filename.is_empty()

func _refresh_benchmarks() -> void:
	benchmark_select.clear()
	var files: Array[String] = store.list_benchmarks()
	for filename in files:
		var parsed: Variant = store.read_json(store.benchmark_path(filename))
		var label := filename
		if typeof(parsed) == TYPE_DICTIONARY:
			label = str(parsed.get("id", filename))
		benchmark_select.add_item(label)
		benchmark_select.set_item_metadata(benchmark_select.item_count - 1, filename)
	if files.is_empty():
		benchmark_status.text = "No benchmark files found in the local workspace."
	else:
		benchmark_status.text = "%d benchmark suite(s) available." % files.size()

func _on_pull_pressed() -> void:
	pull_button.disabled = true
	push_button.disabled = true
	sync_status.text = "Pulling workspace from GitHub…"
	var result: Dictionary = await github_sync.pull_workspace(_github_token())
	pull_button.disabled = false
	push_button.disabled = false
	if result.get("ok", false):
		sync_status.text = "Pulled %d workspace file(s)." % int(result.get("files", 0))
		_refresh_benchmarks()
	else:
		sync_status.text = "Pull failed: " + str(result.get("message", "Unknown error"))
	_refresh_workspace_status()

func _on_push_pressed() -> void:
	var token := _github_token()
	if token.is_empty():
		_on_configure_token_pressed()
		sync_status.text = "Configure a GitHub token before pushing."
		return
	pull_button.disabled = true
	push_button.disabled = true
	sync_status.text = "Pushing outbox…"
	var result: Dictionary = await github_sync.push_outbox(token, _device_id())
	pull_button.disabled = false
	push_button.disabled = false
	if result.get("ok", false):
		sync_status.text = "Pushed %d file(s)." % int(result.get("files", 0))
	else:
		sync_status.text = "Push failed: " + str(result.get("message", "Unknown error"))
	_refresh_workspace_status()

func _on_configure_token_pressed() -> void:
	if bridge == null or not bridge.has_method("saveSecret"):
		token_status.text = "Secure token storage is available in the Android build."
		return
	token_input.text = ""
	token_dialog.popup_centered()

func _on_token_confirmed() -> void:
	if bridge == null:
		return
	var token := token_input.text.strip_edges()
	if token.is_empty():
		bridge.deleteSecret("github_token")
		token_status.text = "GitHub push credential cleared."
	elif bridge.saveSecret("github_token", token):
		token_status.text = "GitHub push credential stored with Android Keystore."
	else:
		token_status.text = "Could not store GitHub credential."
	token_input.text = ""

func _github_token() -> String:
	if bridge != null and bridge.has_method("getSecret"):
		return str(bridge.getSecret("github_token"))
	return ""

func _device_id() -> String:
	if bridge != null and bridge.has_method("deviceId"):
		return str(bridge.deviceId())
	return "editor-test"

func _refresh_workspace_status() -> void:
	var summary: Dictionary = store.workspace_summary()
	data_status.text = "Workspace: %s\nBenchmarks: %d\nOutbox: %d\nResults: %s" % [
		summary.get("workspace_path", ""),
		int(summary.get("benchmarks", 0)),
		int(summary.get("outbox", 0)),
		summary.get("results_path", "")
	]
	if bridge != null and bridge.has_method("getSecret"):
		token_status.text = "GitHub push credential: %s" % ("configured" if not _github_token().is_empty() else "not configured")
	sync_status.text = "%s | %d queued" % [sync_status.text.split(" | ")[0], int(summary.get("outbox", 0))]

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
	run_stats.text = "Backend: %s | Context: %s | Threads: %s | Parameters: %s" % [
		data.get("backend", "CPU"),
		data.get("context", "?"),
		data.get("threads", "?"),
		data.get("parameters", "?")
	]
	_refresh_models()

func _on_model_unloaded(_payload: String) -> void:
	loaded_filename = ""
	_set_status("Model unloaded.")
	run_stats.text = "No model loaded."
	_refresh_models()

func _on_ai_error(payload: String) -> void:
	var data := _json_dict(payload)
	generating = false
	_set_generation_controls(false)
	if benchmark_active:
		benchmark_cancel_requested = true
		_finish_benchmark(false)
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
	if global_status != null:
		global_status.text = text

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
