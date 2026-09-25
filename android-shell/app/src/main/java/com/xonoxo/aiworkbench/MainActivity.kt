package com.xonoxo.aiworkbench

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.JavaScriptReplyProxy
import androidx.webkit.WebMessageCompat
import androidx.webkit.WebSettingsCompat
import androidx.webkit.WebViewAssetLoader
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.Executors

class MainActivity : Activity(), NativeRuntime.Listener {
    companion object {
        private const val APP_ORIGIN = "https://appassets.androidplatform.net"
    }

    private lateinit var webView: WebView
    private lateinit var runtime: NativeRuntime
    private lateinit var updater: BundleUpdater
    private lateinit var secureStore: SecureStore
    private val github = GitHubClient()
    private val ioExecutor = Executors.newCachedThreadPool()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.statusBarColor = Color.rgb(17, 20, 28)
        window.navigationBarColor = Color.rgb(17, 20, 28)

        runtime = NativeRuntime(this).also { it.listener = this }
        updater = BundleUpdater(this)
        secureStore = SecureStore(this)
        secureStore.put("github_client_id", GitHubClient.CLIENT_ID)

        webView = WebView(this)
        webView.setBackgroundColor(Color.rgb(17, 20, 28))
        webView.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
        setContentView(webView)

        configureWebView()
        webView.loadUrl(updater.activeUrl())
    }

    private fun configureWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = false
            allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            mediaPlaybackRequiresUserGesture = true
        }

        if (WebViewFeature.isFeatureSupported(WebViewFeature.SAFE_BROWSING_ENABLE)) {
            WebSettingsCompat.setSafeBrowsingEnabled(webView.settings, true)
        }

        val assetLoader = WebViewAssetLoader.Builder()
            .addPathHandler(
                "/bundled/",
                WebViewAssetLoader.AssetsPathHandler(this)
            )
            .addPathHandler(
                "/current/",
                WebViewAssetLoader.InternalStoragePathHandler(this, updater.currentDir())
            )
            .build()

        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest
            ): WebResourceResponse? = assetLoader.shouldInterceptRequest(request.url)

            @Suppress("DEPRECATION")
            override fun shouldInterceptRequest(
                view: WebView,
                url: String
            ): WebResourceResponse? = assetLoader.shouldInterceptRequest(Uri.parse(url))

            override fun shouldOverrideUrlLoading(
                view: WebView,
                request: WebResourceRequest
            ): Boolean {
                val uri = request.url
                if (uri.scheme == "https" && uri.host == "appassets.androidplatform.net") {
                    return false
                }
                startActivity(Intent(Intent.ACTION_VIEW, uri))
                return true
            }
        }

        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            throw IllegalStateException(
                "This Android WebView is too old for the secure workbench bridge"
            )
        }

        WebViewCompat.addWebMessageListener(
            webView,
            "WorkbenchNative",
            setOf(APP_ORIGIN),
            object : WebViewCompat.WebMessageListener {
                override fun onPostMessage(
                    view: WebView,
                    message: WebMessageCompat,
                    sourceOrigin: Uri,
                    isMainFrame: Boolean,
                    replyProxy: JavaScriptReplyProxy
                ) {
                    if (!isMainFrame || sourceOrigin.scheme != "https" || sourceOrigin.host != "appassets.androidplatform.net") return
                    handleRequest(message.data ?: "")
                }
            }
        )
    }

    private fun handleRequest(raw: String) {
        val request = try {
            JSONObject(raw)
        } catch (_: Throwable) {
            return
        }

        val id = request.optString("id")
        val type = request.optString("type")
        val payload = request.optJSONObject("payload") ?: JSONObject()

        fun ok(data: Any? = JSONObject()) = reply(id, true, data, null)
        fun fail(t: Throwable) =
            reply(id, false, null, t.message ?: t.javaClass.simpleName)

        when (type) {
            "kernel.info" -> ok(
                JSONObject()
                    .put("kernel_version", BundleUpdater.KERNEL_VERSION)
                    .put("workbench_version", updater.currentVersion())
                    .put("runtime", runtime.systemInfo())
                    .put("device_id", deviceId())
            )

            "models.list" -> ok(runtime.listLocalModels())

            "model.download" -> {
                runtime.downloadModel(
                    payload.getString("id"),
                    payload.getString("url"),
                    payload.getString("filename"),
                    payload.optString("sha256")
                ) { result ->
                    runOnUiThread {
                        result.onSuccess { ok(it) }
                        result.onFailure { fail(it) }
                    }
                }
            }

            "model.download.cancel" -> {
                runtime.cancelDownload()
                ok()
            }

            "model.delete" -> ok(
                JSONObject().put(
                    "deleted",
                    runtime.deleteModel(payload.getString("filename"))
                )
            )

            "model.load" -> {
                val path = runtime.modelPath(payload.getString("filename"))
                if (path.isBlank()) {
                    fail(IllegalStateException("Model is not downloaded"))
                } else {
                    runtime.loadModel(
                        path,
                        payload.optInt("context", 2048),
                        payload.optInt("threads", 4)
                    ) { result ->
                        runOnUiThread {
                            val parsed = JSONObject(result)
                            if (parsed.optBoolean("ok")) {
                                ok(parsed)
                            } else {
                                fail(
                                    IllegalStateException(
                                        parsed.optString("message", "Load failed")
                                    )
                                )
                            }
                        }
                    }
                }
            }

            "model.unload" -> runtime.unload { runOnUiThread { ok() } }

            "generation.start" -> {
                runtime.generate(
                    payload.getString("prompt"),
                    payload.optInt("max_tokens", 256),
                    payload.optDouble("temperature", 0.7).toFloat(),
                    payload.optDouble("top_p", 0.95).toFloat(),
                    payload.optInt("top_k", 40),
                    payload.optDouble("repeat_penalty", 1.1).toFloat()
                ) { result ->
                    runOnUiThread {
                        val parsed = JSONObject(result)
                        if (parsed.optBoolean("ok")) {
                            ok(parsed)
                        } else {
                            fail(
                                IllegalStateException(
                                    parsed.optString("message", "Generation failed")
                                )
                            )
                        }
                    }
                }
            }

            "generation.stop" -> {
                runtime.stopGeneration()
                ok()
            }

            "update.check" -> ioExecutor.execute {
                try {
                    val data = updater.check()
                    runOnUiThread { ok(data) }
                } catch (t: Throwable) {
                    runOnUiThread { fail(t) }
                }
            }

            "update.apply" -> ioExecutor.execute {
                try {
                    val manifest = payload.getJSONObject("manifest")
                    val data = updater.apply(manifest)
                    runOnUiThread { ok(data) }
                } catch (t: Throwable) {
                    runOnUiThread { fail(t) }
                }
            }

            "update.reload" -> {
                webView.loadUrl(updater.activeUrl())
                ok()
            }

            "secret.set" -> {
                try {
                    secureStore.put(payload.getString("name"), payload.optString("value"))
                    ok()
                } catch (t: Throwable) {
                    fail(t)
                }
            }

            "secret.get" -> {
                try {
                    ok(
                        JSONObject().put(
                            "value",
                            secureStore.get(payload.getString("name"))
                        )
                    )
                } catch (t: Throwable) {
                    fail(t)
                }
            }

            "secret.delete" -> {
                secureStore.delete(payload.getString("name"))
                ok()
            }

            "github.setupInfo" -> {
                ok(githubSetupInfo())
            }

            "github.openUrl" -> {
                try {
                    openGitHubUrl(payload.getString("url"))
                    ok()
                } catch (t: Throwable) {
                    fail(t)
                }
            }

            "github.discoverApp" -> ioExecutor.execute {
                try {
                    val slug = githubAppSlug()
                    val app = github.discoverApp(slug)
                    val clientId = app.getString("client_id")
                    secureStore.put("github_client_id", clientId)
                    runOnUiThread {
                        ok(
                            githubSetupInfo()
                                .put("app_discovered", true)
                                .put("client_id", clientId)
                        )
                    }
                } catch (t: Throwable) {
                    runOnUiThread { fail(t) }
                }
            }

            "github.deviceStart" -> ioExecutor.execute {
                try {
                    val slug = githubAppSlug()
                    var clientId = secureStore.get("github_client_id")
                    if (clientId.isBlank()) {
                        val app = github.discoverApp(slug)
                        clientId = app.getString("client_id")
                        secureStore.put("github_client_id", clientId)
                    }

                    val device = github.requestDeviceCode(clientId)
                    if (device.has("error")) {
                        throw IllegalStateException(githubAuthError(device))
                    }

                    secureStore.put("github_device_code", device.getString("device_code"))
                    secureStore.put(
                        "github_device_interval",
                        device.optInt("interval", 5).toString()
                    )
                    secureStore.put(
                        "github_device_expires_at",
                        (System.currentTimeMillis() +
                            device.optLong("expires_in", 900L) * 1000L).toString()
                    )

                    runOnUiThread {
                        ok(
                            JSONObject()
                                .put("status", "waiting")
                                .put("user_code", device.getString("user_code"))
                                .put(
                                    "verification_uri",
                                    device.optString(
                                        "verification_uri",
                                        "https://github.com/login/device"
                                    )
                                )
                                .put("interval", device.optInt("interval", 5))
                                .put("expires_in", device.optInt("expires_in", 900))
                        )
                    }
                } catch (t: Throwable) {
                    runOnUiThread { fail(t) }
                }
            }

            "github.devicePoll" -> ioExecutor.execute {
                try {
                    val clientId = secureStore.get("github_client_id")
                    val deviceCode = secureStore.get("github_device_code")
                    val expiresAt = secureStore.get("github_device_expires_at")
                        .toLongOrNull() ?: 0L
                    if (deviceCode.isBlank()) {
                        throw IllegalStateException("No GitHub authorization is in progress")
                    }
                    if (expiresAt > 0L && System.currentTimeMillis() >= expiresAt) {
                        clearGitHubDeviceSession()
                        throw IllegalStateException("GitHub authorization code expired")
                    }

                    val result = github.pollDeviceCode(clientId, deviceCode)
                    val error = result.optString("error")
                    if (error.isNotBlank()) {
                        when (error) {
                            "authorization_pending" -> runOnUiThread {
                                ok(
                                    JSONObject()
                                        .put("status", "pending")
                                        .put(
                                            "interval",
                                            secureStore.get("github_device_interval")
                                                .toIntOrNull() ?: 5
                                        )
                                )
                            }

                            "slow_down" -> {
                                val next = (secureStore.get("github_device_interval")
                                    .toIntOrNull() ?: 5) + 5
                                secureStore.put("github_device_interval", next.toString())
                                runOnUiThread {
                                    ok(
                                        JSONObject()
                                            .put("status", "pending")
                                            .put("interval", next)
                                    )
                                }
                            }

                            else -> {
                                clearGitHubDeviceSession()
                                throw IllegalStateException(githubAuthError(result))
                            }
                        }
                    } else {
                        saveGitHubTokens(result)
                        clearGitHubDeviceSession()
                        val token = ensureGitHubToken()
                        val status = github.connectionStatus(token, githubAppSlug())
                        runOnUiThread {
                            ok(
                                status
                                    .put("status", "authorized")
                                    .put("app_slug", githubAppSlug())
                            )
                        }
                    }
                } catch (t: Throwable) {
                    runOnUiThread { fail(t) }
                }
            }

            "github.status" -> ioExecutor.execute {
                try {
                    val setup = githubSetupInfo()
                    val token = ensureGitHubToken()
                    if (token.isBlank()) {
                        runOnUiThread {
                            ok(
                                setup
                                    .put("signed_in", false)
                                    .put("repo_access", false)
                            )
                        }
                    } else {
                        val status = github.connectionStatus(token, githubAppSlug())
                        val keys = status.keys()
                        while (keys.hasNext()) {
                            val key = keys.next()
                            setup.put(key, status.get(key))
                        }
                        runOnUiThread { ok(setup) }
                    }
                } catch (t: Throwable) {
                    runOnUiThread {
                        ok(
                            githubSetupInfo()
                                .put("signed_in", false)
                                .put("repo_access", false)
                                .put("error", t.message ?: "GitHub status failed")
                        )
                    }
                }
            }

            "github.signOut" -> {
                clearGitHubTokens()
                ok(githubSetupInfo().put("signed_in", false))
            }

            "clipboard.copy" -> {
                try {
                    val manager =
                        getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    manager.setPrimaryClip(
                        ClipData.newPlainText(
                            payload.optString("label", "AI Workbench"),
                            payload.getString("text")
                        )
                    )
                    ok()
                } catch (t: Throwable) {
                    fail(t)
                }
            }

            "github.pushResult" -> ioExecutor.execute {
                try {
                    val token = ensureGitHubToken()
                    val data = github.pushResult(
                        token,
                        deviceId(),
                        payload.optString(
                            "filename",
                            "result-${System.currentTimeMillis()}.json"
                        ),
                        payload.getString("content")
                    )
                    runOnUiThread { ok(data) }
                } catch (t: Throwable) {
                    runOnUiThread { fail(t) }
                }
            }

            else -> fail(
                IllegalArgumentException("Unknown kernel request: $type")
            )
        }
    }

    private fun githubAppSlug(): String = GitHubClient.APP_SLUG

    private fun githubSetupInfo(): JSONObject {
        val slug = githubAppSlug()
        val registration = Uri.parse("https://github.com/settings/apps/new")
            .buildUpon()
            .appendQueryParameter("name", slug)
            .appendQueryParameter(
                "description",
                "Device-specific AI Workbench connection for uploading benchmark results."
            )
            .appendQueryParameter(
                "url",
                "https://github.com/${GitHubClient.OWNER}/${GitHubClient.REPO}"
            )
            .appendQueryParameter("public", "true")
            .appendQueryParameter("webhook_active", "false")
            .appendQueryParameter("contents", "write")
            .build()
            .toString()

        val clientId = try {
            secureStore.get("github_client_id")
        } catch (_: Throwable) {
            ""
        }

        return JSONObject()
            .put("app_slug", slug)
            .put("client_id", clientId)
            .put("app_discovered", clientId.isNotBlank())
            .put("registration_url", registration)
            .put("settings_url", "https://github.com/settings/apps/$slug")
            .put("install_url", "https://github.com/apps/$slug/installations/new")
            .put("verification_url", "https://github.com/login/device")
            .put("target_repo", "${GitHubClient.OWNER}/${GitHubClient.REPO}")
    }

    private fun openGitHubUrl(url: String) {
        val uri = Uri.parse(url)
        require(uri.scheme == "https" && uri.host == "github.com") {
            "Only github.com authorization links may be opened"
        }
        startActivity(Intent(Intent.ACTION_VIEW, uri))
    }

    private fun saveGitHubTokens(payload: JSONObject) {
        val accessToken = payload.optString("access_token")
        require(accessToken.isNotBlank()) { "GitHub did not return an access token" }
        secureStore.put("github_token", accessToken)

        val refreshToken = payload.optString("refresh_token")
        if (refreshToken.isNotBlank()) {
            secureStore.put("github_refresh_token", refreshToken)
        }

        val expiresIn = payload.optLong("expires_in", 0L)
        if (expiresIn > 0L) {
            secureStore.put(
                "github_token_expires_at",
                (System.currentTimeMillis() + expiresIn * 1000L).toString()
            )
        } else {
            secureStore.delete("github_token_expires_at")
        }

        val refreshExpiresIn = payload.optLong("refresh_token_expires_in", 0L)
        if (refreshExpiresIn > 0L) {
            secureStore.put(
                "github_refresh_expires_at",
                (System.currentTimeMillis() + refreshExpiresIn * 1000L).toString()
            )
        }
    }

    private fun ensureGitHubToken(): String {
        var token = secureStore.get("github_token")
        if (token.isBlank()) return ""

        val expiresAt = secureStore.get("github_token_expires_at")
            .toLongOrNull() ?: 0L

        if (expiresAt > 0L && System.currentTimeMillis() + 120_000L >= expiresAt) {
            val clientId = secureStore.get("github_client_id")
            val refreshToken = secureStore.get("github_refresh_token")
            if (clientId.isBlank() || refreshToken.isBlank()) {
                clearGitHubTokens()
                return ""
            }
            val refreshed = github.refreshUserToken(clientId, refreshToken)
            if (refreshed.has("error")) {
                clearGitHubTokens()
                throw IllegalStateException(githubAuthError(refreshed))
            }
            saveGitHubTokens(refreshed)
            token = secureStore.get("github_token")
        }

        return token
    }

    private fun clearGitHubDeviceSession() {
        secureStore.delete("github_device_code")
        secureStore.delete("github_device_interval")
        secureStore.delete("github_device_expires_at")
    }

    private fun clearGitHubTokens() {
        secureStore.delete("github_token")
        secureStore.delete("github_refresh_token")
        secureStore.delete("github_token_expires_at")
        secureStore.delete("github_refresh_expires_at")
        clearGitHubDeviceSession()
    }

    private fun githubAuthError(payload: JSONObject): String {
        return when (payload.optString("error")) {
            "device_flow_disabled" ->
                "Enable Device Flow in the GitHub App settings, then try Sign in again."
            "expired_token" ->
                "The GitHub authorization code expired. Start sign-in again."
            "access_denied" ->
                "GitHub authorization was cancelled."
            "incorrect_client_credentials" ->
                "The GitHub connection's client ID is invalid."
            else -> payload.optString(
                "error_description",
                payload.optString("error", "GitHub authorization failed")
            )
        }
    }

    override fun onTokenChunk(chunk: String) {
        runOnUiThread {
            emit("token", JSONObject().put("chunk", chunk))
        }
    }

    override fun onDownloadProgress(payload: JSONObject) {
        runOnUiThread {
            emit("download_progress", payload)
        }
    }

    private fun reply(
        id: String,
        ok: Boolean,
        data: Any?,
        error: String?
    ) {
        val payload = JSONObject()
            .put("id", id)
            .put("ok", ok)
        if (data != null) payload.put("data", data)
        if (error != null) payload.put("error", error)
        emit("reply", payload)
    }

    private fun emit(type: String, payload: Any) {
        val event = JSONObject()
            .put("type", type)
            .put("payload", payload)
            .toString()
        val quoted = JSONObject.quote(event)
        webView.evaluateJavascript(
            "window.__nativeEvent && window.__nativeEvent(JSON.parse($quoted));",
            null
        )
    }

    private fun deviceId(): String {
        val prefs = getSharedPreferences(
            "ai_workbench_identity",
            Context.MODE_PRIVATE
        )
        val existing = prefs.getString("device_id", null)
        if (!existing.isNullOrBlank()) return existing

        val created = UUID.randomUUID().toString()
        prefs.edit().putString("device_id", created).apply()
        return created
    }

    override fun onDestroy() {
        runtime.shutdown()
        ioExecutor.shutdownNow()
        webView.destroy()
        super.onDestroy()
    }
}
