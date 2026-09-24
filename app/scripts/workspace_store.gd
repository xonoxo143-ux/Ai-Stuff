extends RefCounted

const LOCAL_WORKSPACE := "user://workspace"
const OUTBOX := "user://outbox"
const SENT := "user://sent"
const RESULTS := "user://results"

func initialize() -> void:
	_ensure_dir(LOCAL_WORKSPACE)
	_ensure_dir(OUTBOX)
	_ensure_dir(SENT)
	_ensure_dir(RESULTS)
	_seed_missing("res://workspace", LOCAL_WORKSPACE)

func list_benchmarks() -> Array[String]:
	var found: Array[String] = []
	var root := LOCAL_WORKSPACE + "/benchmarks"
	var dir := DirAccess.open(root)
	if dir == null:
		return found
	dir.list_dir_begin()
	while true:
		var name := dir.get_next()
		if name.is_empty():
			break
		if not dir.current_is_dir() and name.to_lower().ends_with(".json"):
			found.append(name)
	dir.list_dir_end()
	found.sort()
	return found

func benchmark_path(filename: String) -> String:
	return LOCAL_WORKSPACE + "/benchmarks/" + filename.get_file()

func read_json(path: String) -> Variant:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return null
	return JSON.parse_string(file.get_as_text())

func write_text(path: String, content: String) -> bool:
	var parent := path.get_base_dir()
	if not parent.is_empty():
		_ensure_dir(parent)
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(content)
	return true

func queue_result(payload: Dictionary, prefix: String = "benchmark") -> String:
	var stamp := Time.get_datetime_string_from_system(true).replace(":", "-")
	var nonce := str(Time.get_ticks_usec())
	var filename := "%s-%s-%s.json" % [prefix, stamp, nonce]
	var result_path := RESULTS + "/" + filename
	var content := JSON.stringify(payload, "\t")
	write_text(result_path, content)
	write_text(OUTBOX + "/" + filename, content)
	return result_path

func outbox_files() -> Array[String]:
	var found: Array[String] = []
	_collect_files(OUTBOX, found)
	found.sort()
	return found

func mark_sent(path: String) -> bool:
	if not path.begins_with(OUTBOX + "/"):
		return false
	var target := SENT + "/" + path.get_file()
	if FileAccess.file_exists(target):
		target = SENT + "/" + str(Time.get_ticks_usec()) + "-" + path.get_file()
	var err := DirAccess.rename_absolute(path, target)
	return err == OK

func workspace_summary() -> Dictionary:
	return {
		"benchmarks": list_benchmarks().size(),
		"outbox": outbox_files().size(),
		"workspace_path": LOCAL_WORKSPACE,
		"results_path": RESULTS
	}

func _seed_missing(source: String, destination: String) -> void:
	var dir := DirAccess.open(source)
	if dir == null:
		return
	_ensure_dir(destination)
	dir.list_dir_begin()
	while true:
		var name := dir.get_next()
		if name.is_empty():
			break
		if name == "." or name == "..":
			continue
		var src := source + "/" + name
		var dst := destination + "/" + name
		if dir.current_is_dir():
			_seed_missing(src, dst)
		elif not FileAccess.file_exists(dst):
			var input := FileAccess.open(src, FileAccess.READ)
			if input != null:
				write_text(dst, input.get_as_text())
	dir.list_dir_end()

func _collect_files(root: String, output: Array[String]) -> void:
	var dir := DirAccess.open(root)
	if dir == null:
		return
	dir.list_dir_begin()
	while true:
		var name := dir.get_next()
		if name.is_empty():
			break
		if name == "." or name == "..":
			continue
		var path := root + "/" + name
		if dir.current_is_dir():
			_collect_files(path, output)
		else:
			output.append(path)
	dir.list_dir_end()

func _ensure_dir(path: String) -> void:
	if DirAccess.dir_exists_absolute(path):
		return
	DirAccess.make_dir_recursive_absolute(path)
