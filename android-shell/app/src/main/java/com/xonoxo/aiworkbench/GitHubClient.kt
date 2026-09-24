package com.xonoxo.aiworkbench

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Base64

class GitHubClient {
    companion object {
        private const val OWNER = "xonoxo143-ux"
        private const val REPO = "Ai-Stuff"
        private const val BRANCH = "aistuff"
        private const val API = "https://api.github.com"
    }

    fun pushResult(
        token: String,
        deviceId: String,
        filename: String,
        content: String
    ): JSONObject {
        require(token.isNotBlank()) { "GitHub token is not configured" }

        val safeDevice = safe(deviceId)
        val safeFilename = safe(filename).let {
            if (it.endsWith(".json")) it else "$it.json"
        }
        val remote = "devices/$safeDevice/results/$safeFilename"
        val url = URL("$API/repos/$OWNER/$REPO/contents/$remote")
        val connection = url.openConnection() as HttpURLConnection
        connection.requestMethod = "PUT"
        connection.connectTimeout = 30_000
        connection.readTimeout = 60_000
        connection.doOutput = true
        connection.setRequestProperty("Accept", "application/vnd.github+json")
        connection.setRequestProperty("Authorization", "Bearer ${token.trim()}")
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
        connection.setRequestProperty("User-Agent", "AIWorkbenchKernel/1")
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
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        connection.disconnect()

        if (code !in 200..299) {
            throw IllegalStateException("GitHub HTTP $code: $response")
        }
        return JSONObject(response)
    }

    private fun safe(value: String): String {
        return value.lowercase()
            .map { ch -> if (ch.isLetterOrDigit() || ch == '-' || ch == '_' || ch == '.') ch else '-' }
            .joinToString("")
            .take(100)
    }
}
