package com.xonoxo.aiworkbench

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Base64

class GitHubClient {
    companion object {
        const val OWNER = "xonoxo143-ux"
        const val REPO = "Ai-Stuff"
        const val BRANCH = "aistuff"
        const val CLIENT_ID = "Iv23lio4I0nxZZWQZsAv"
        const val API = "https://api.github.com"
        const val API_VERSION = "2026-03-10"
    }

    fun discoverApp(slug: String): JSONObject {
        val connection = request("$API/apps/${urlPath(slug)}")
        val response = readJson(connection)
        if (connection.responseCode !in 200..299) {
            throw IllegalStateException("GitHub could not find the AI Workbench app yet.")
        }
        return response
    }

    fun requestDeviceCode(clientId: String): JSONObject {
        require(clientId.isNotBlank()) { "GitHub client ID is missing" }
        return postForm(
            "https://github.com/login/device/code",
            mapOf("client_id" to clientId)
        )
    }

    fun pollDeviceCode(clientId: String, deviceCode: String): JSONObject {
        require(clientId.isNotBlank()) { "GitHub client ID is missing" }
        require(deviceCode.isNotBlank()) { "GitHub device session is missing" }
        return postForm(
            "https://github.com/login/oauth/access_token",
            mapOf(
                "client_id" to clientId,
                "device_code" to deviceCode,
                "grant_type" to "urn:ietf:params:oauth:grant-type:device_code"
            )
        )
    }

    fun refreshUserToken(clientId: String, refreshToken: String): JSONObject {
        require(clientId.isNotBlank()) { "GitHub client ID is missing" }
        require(refreshToken.isNotBlank()) { "GitHub refresh token is missing" }
        return postForm(
            "https://github.com/login/oauth/access_token",
            mapOf(
                "client_id" to clientId,
                "grant_type" to "refresh_token",
                "refresh_token" to refreshToken
            )
        )
    }

    fun connectionStatus(token: String, appSlug: String): JSONObject {
        require(token.isNotBlank()) { "GitHub is not signed in" }

        val userConnection = request("$API/user", token)
        val user = readJson(userConnection)
        if (userConnection.responseCode !in 200..299) {
            throw IllegalStateException(
                if (userConnection.responseCode == 401) "GitHub sign-in expired"
                else "GitHub user check failed (${userConnection.responseCode})"
            )
        }

        val installsConnection = request("$API/user/installations?per_page=100", token)
        val installs = readJson(installsConnection)
        if (installsConnection.responseCode !in 200..299) {
            throw IllegalStateException("Could not read GitHub App installations")
        }

        var matchingInstallation: JSONObject? = null
        val installationArray = installs.optJSONArray("installations") ?: JSONArray()
        for (i in 0 until installationArray.length()) {
            val item = installationArray.optJSONObject(i) ?: continue
            if (item.optString("app_slug") == appSlug) {
                matchingInstallation = item
                break
            }
        }

        var repoAccess = false
        var repoPermission = ""
        var installationId = 0L

        if (matchingInstallation != null) {
            installationId = matchingInstallation.optLong("id", 0L)
            if (installationId > 0L) {
                val reposConnection = request(
                    "$API/user/installations/$installationId/repositories?per_page=100",
                    token
                )
                val repos = readJson(reposConnection)
                if (reposConnection.responseCode in 200..299) {
                    val repositoryArray = repos.optJSONArray("repositories") ?: JSONArray()
                    for (i in 0 until repositoryArray.length()) {
                        val repository = repositoryArray.optJSONObject(i) ?: continue
                        if (repository.optString("full_name").equals("$OWNER/$REPO", true)) {
                            repoAccess = true
                            val permissions = repository.optJSONObject("permissions")
                            repoPermission = when {
                                permissions?.optBoolean("admin") == true -> "admin"
                                permissions?.optBoolean("push") == true -> "write"
                                permissions?.optBoolean("pull") == true -> "read"
                                else -> ""
                            }
                            break
                        }
                    }
                }
            }
        }

        return JSONObject()
            .put("signed_in", true)
            .put("login", user.optString("login"))
            .put("avatar_url", user.optString("avatar_url"))
            .put("app_installed", matchingInstallation != null)
            .put("installation_id", installationId)
            .put("repo_access", repoAccess)
            .put("repo_permission", repoPermission)
    }

    fun pushResult(
        token: String,
        deviceId: String,
        filename: String,
        content: String
    ): JSONObject {
        require(token.isNotBlank()) { "GitHub is not signed in" }

        val safeDevice = safe(deviceId)
        val safeFilename = safe(filename).let {
            if (it.endsWith(".json")) it else "$it.json"
        }
        val remote = "devices/$safeDevice/results/$safeFilename"
        val url = URL("$API/repos/$OWNER/$REPO/contents/$remote")
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "PUT"
        configure(connection, token)
        connection.readTimeout = 60_000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")

        val body = JSONObject()
            .put("message", "Upload AI Workbench result from $safeDevice")
            .put(
                "content",
                Base64.getEncoder().encodeToString(content.toByteArray(Charsets.UTF_8))
            )
            .put("branch", BRANCH)
            .toString()

        connection.outputStream.use {
            it.write(body.toByteArray(Charsets.UTF_8))
        }

        val code = connection.responseCode
        val response = readBody(connection)
        connection.disconnect()

        if (code !in 200..299) {
            val detail = try {
                JSONObject(response).optString("message", response)
            } catch (_: Throwable) {
                response
            }
            throw IllegalStateException("GitHub upload failed ($code): $detail")
        }
        return JSONObject(response)
    }

    private fun request(url: String, token: String = ""): HttpURLConnection {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        configure(connection, token)
        connection.connect()
        return connection
    }

    private fun postForm(url: String, values: Map<String, String>): JSONObject {
        val body = values.entries.joinToString("&") {
            "${form(it.key)}=${form(it.value)}"
        }
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        configure(connection)
        connection.doOutput = true
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty(
            "Content-Type",
            "application/x-www-form-urlencoded"
        )
        connection.outputStream.use {
            it.write(body.toByteArray(Charsets.UTF_8))
        }
        val code = connection.responseCode
        val response = readBody(connection)
        connection.disconnect()

        if (response.isBlank()) {
            throw IllegalStateException("GitHub returned an empty authentication response")
        }
        val json = JSONObject(response)
        if (code !in 200..299 && !json.has("error")) {
            throw IllegalStateException("GitHub authentication HTTP $code")
        }
        return json
    }

    private fun configure(connection: HttpURLConnection, token: String = "") {
        connection.connectTimeout = 30_000
        connection.readTimeout = 30_000
        connection.setRequestProperty("Accept", "application/vnd.github+json")
        connection.setRequestProperty("X-GitHub-Api-Version", API_VERSION)
        connection.setRequestProperty("User-Agent", "AIWorkbenchKernel/2")
        if (token.isNotBlank()) {
            connection.setRequestProperty("Authorization", "Bearer ${token.trim()}")
        }
    }

    private fun readJson(connection: HttpURLConnection): JSONObject {
        val body = readBody(connection)
        return if (body.isBlank()) JSONObject() else JSONObject(body)
    }

    private fun readBody(connection: HttpURLConnection): String {
        val code = connection.responseCode
        val stream = if (code in 200..299) {
            connection.inputStream
        } else {
            connection.errorStream
        }
        return stream?.bufferedReader()?.use { it.readText() }.orEmpty()
    }

    private fun form(value: String): String =
        URLEncoder.encode(value, Charsets.UTF_8.name())

    private fun urlPath(value: String): String =
        value.replace(Regex("[^A-Za-z0-9_.-]"), "-")

    private fun safe(value: String): String {
        return value.lowercase()
            .map { ch ->
                if (ch.isLetterOrDigit() || ch == '-' || ch == '_' || ch == '.') ch else '-'
            }
            .joinToString("")
            .take(100)
    }
}
