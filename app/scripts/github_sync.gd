extends Node

const OWNER := "xonoxo143-ux"
const REPO := "Ai-Stuff"
const BRANCH := "aistuff"
const API := "https://api.github.com"

var store: RefCounted

func configure(workspace_store: RefCounted) -> void:
	store = workspace_store

func pull_workspace(token: String = "") -> Dictionary:
	var headers := _headers(token)
	var tree_url := "%s/repos/%s/%s/git/trees/%s?recursive=1" % [API, OWNER, REPO, BRANCH]
	var tree_response := await _request(tree_url, headers)
	if not tree_response.get("ok", false):
		return tree_response
	var tree_data: Variant = JSON.parse_string(tree_response.get("body", ""))
	if typeof(tree_data) != TYPE_DICTIONARY:
		return {"ok": false, "message": "GitHub tree response was not JSON."}
	var entries: Array = tree_data.get("tree", [])
	var copied := 0
	for entry in entries:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var path := str(entry.get("path", ""))
		if entry.get("type", "") != "blob" or not path.begins_with("workspace/"):
			continue
		if int(entry.get("size", 0)) > 2 * 1024 * 1024:
			continue
		var sha := str(entry.get("sha", ""))
		if sha.is_empty():
			continue
		var blob_url := "%s/repos/%s/%s/git/blobs/%s" % [API, OWNER, REPO, sha]
		var blob_response := await _request(blob_url, headers)
		if not blob_response.get("ok", false):
			return {"ok": false, "message": "Pull failed at %s: %s" % [path, blob_response.get("message", "HTTP error")]}
		var blob: Variant = JSON.parse_string(blob_response.get("body", ""))
		if typeof(blob) != TYPE_DICTIONARY or str(blob.get("encoding", "")) != "base64":
			return {"ok": false, "message": "Unsupported blob encoding for " + path}
		var encoded := str(blob.get("content", "")).replace("\n", "")
		var bytes := Marshalls.base64_to_raw(encoded)
		var relative := path.trim_prefix("workspace/")
		if relative.contains(".."):
			return {"ok": false, "message": "Rejected unsafe workspace path."}
		if not store.write_text("user://workspace/" + relative, bytes.get_string_from_utf8()):
			return {"ok": false, "message": "Could not write " + relative}
		copied += 1
	return {"ok": true, "files": copied, "tree_sha": str(tree_data.get("sha", ""))}

func push_outbox(token: String, device_id: String) -> Dictionary:
	if token.strip_edges().is_empty():
		return {"ok": false, "needs_token": true, "message": "A GitHub token is required to push results."}
	var files: Array[String] = store.outbox_files()
	if files.is_empty():
		return {"ok": true, "files": 0, "message": "Outbox is empty."}
	var pushed := 0
	for path in files:
		var input := FileAccess.open(path, FileAccess.READ)
		if input == null:
			continue
		var content := input.get_as_text()
		var remote := "devices/%s/results/%s" % [_safe_component(device_id), path.get_file()]
		var url := "%s/repos/%s/%s/contents/%s" % [API, OWNER, REPO, remote]
		var body := JSON.stringify({
			"message": "Upload workbench result from " + _safe_component(device_id),
			"content": Marshalls.raw_to_base64(content.to_utf8_buffer()),
			"branch": BRANCH
		})
		var response := await _request(url, _headers(token), HTTPClient.METHOD_PUT, body)
		if not response.get("ok", false):
			return {"ok": false, "files": pushed, "message": "Push failed at %s: %s" % [path.get_file(), response.get("message", "HTTP error")]}
		store.mark_sent(path)
		pushed += 1
	return {"ok": true, "files": pushed}

func _headers(token: String) -> PackedStringArray:
	var result := PackedStringArray([
		"Accept: application/vnd.github+json",
		"X-GitHub-Api-Version: 2022-11-28",
		"User-Agent: LocalAIWorkbench/0.2"
	])
	if not token.strip_edges().is_empty():
		result.append("Authorization: Bearer " + token.strip_edges())
	return result

func _request(url: String, headers: PackedStringArray, method: int = HTTPClient.METHOD_GET, body: String = "") -> Dictionary:
	var request := HTTPRequest.new()
	request.timeout = 60.0
	add_child(request)
	var err := request.request(url, headers, method, body)
	if err != OK:
		request.queue_free()
		return {"ok": false, "message": "Request could not start: " + error_string(err)}
	var completed: Array = await request.request_completed
	request.queue_free()
	var result_code := int(completed[0])
	var response_code := int(completed[1])
	var response_body: PackedByteArray = completed[3]
	var text := response_body.get_string_from_utf8()
	if result_code != HTTPRequest.RESULT_SUCCESS:
		return {"ok": false, "code": response_code, "message": "Network result %s" % result_code, "body": text}
	if response_code < 200 or response_code >= 300:
		return {"ok": false, "code": response_code, "message": "GitHub HTTP %s" % response_code, "body": text}
	return {"ok": true, "code": response_code, "body": text}

func _safe_component(value: String) -> String:
	var safe := ""
	for ch in value:
		if ch.to_lower() in "abcdefghijklmnopqrstuvwxyz0123456789-_":
			safe += ch
		else:
			safe += "-"
	return safe.left(80)
