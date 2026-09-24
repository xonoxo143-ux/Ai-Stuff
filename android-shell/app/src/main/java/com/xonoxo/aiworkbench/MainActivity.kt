package com.xonoxo.aiworkbench

import android.app.Activity
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
                    if (!isMainFrame || sourceOrigin.toString() != APP_ORIGIN) return
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

            "github.pushResult" -> ioExecutor.execute {
                try {
                    val token = secureStore.get("github_token")
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
