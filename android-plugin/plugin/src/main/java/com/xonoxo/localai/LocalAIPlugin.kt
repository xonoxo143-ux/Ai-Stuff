package com.xonoxo.localai

import android.util.Log
import org.godotengine.godot.Godot
import org.godotengine.godot.plugin.GodotPlugin
import org.godotengine.godot.plugin.SignalInfo
import org.godotengine.godot.plugin.UsedByGodot
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class LocalAIPlugin(godot: Godot) : GodotPlugin(godot) {
    companion object {
        private const val TAG = "LocalAI"
        private val DOWNLOAD_PROGRESS = SignalInfo("download_progress", String::class.java)
        private val DOWNLOAD_FINISHED = SignalInfo("download_finished", String::class.java)
        private val DOWNLOAD_FAILED = SignalInfo("download_failed", String::class.java)
        private val MODELS_CHANGED = SignalInfo("models_changed", String::class.java)
        private val MODEL_LOADED = SignalInfo("model_loaded", String::class.java)
        private val MODEL_UNLOADED = SignalInfo("model_unloaded", String::class.java)
        private val TOKEN_RECEIVED = SignalInfo("token_received", String::class.java)
        private val GENERATION_FINISHED = SignalInfo("generation_finished", String::class.java)
        private val AI_ERROR = SignalInfo("ai_error", String::class.java)

        init {
            System.loadLibrary("local_ai")
        }
    }

    private val inferenceExecutor = Executors.newSingleThreadExecutor()
    private val ioExecutor = Executors.newSingleThreadExecutor()
    private val downloadCancelled = AtomicBoolean(false)
    private val modelsDir: File by lazy {
        val appContext = getContext()
        File(appContext.getExternalFilesDir(null) ?: appContext.filesDir, "models").apply { mkdirs() }
    }

    override fun getPluginName() = BuildConfig.GODOT_PLUGIN_NAME

    override fun getPluginSignals(): Set<SignalInfo?> = setOf(
        DOWNLOAD_PROGRESS,
        DOWNLOAD_FINISHED,
        DOWNLOAD_FAILED,
        MODELS_CHANGED,
        MODEL_LOADED,
        MODEL_UNLOADED,
        TOKEN_RECEIVED,
        GENERATION_FINISHED,
        AI_ERROR
    )

    @UsedByGodot
    fun downloadModel(modelId: String, url: String, filename: String, sha256: String) {
        downloadCancelled.set(false)
        ioExecutor.execute {
            val safeName = File(filename).name
            val finalFile = File(modelsDir, safeName)
            val partFile = File(modelsDir, "$safeName.part")
            try {
                if (finalFile.exists() && (sha256.isBlank() || sha256(finalFile).equals(sha256, true))) {
                    emit(DOWNLOAD_FINISHED, JSONObject()
                        .put("id", modelId)
                        .put("filename", safeName)
                        .put("path", finalFile.absolutePath)
                        .put("cached", true)
                        .toString())
                    emit(MODELS_CHANGED, listLocalModels())
                    return@execute
                }

                var existing = if (partFile.exists()) partFile.length() else 0L
                val connection = URL(url).openConnection() as HttpURLConnection
                connection.instanceFollowRedirects = true
                connection.connectTimeout = 30_000
                connection.readTimeout = 60_000
                connection.setRequestProperty("User-Agent", "LocalAIWorkbench/0.1")
                if (existing > 0L) {
                    connection.setRequestProperty("Range", "bytes=$existing-")
                }
                connection.connect()

                val append = existing > 0L && connection.responseCode == HttpURLConnection.HTTP_PARTIAL
                if (!append) {
                    existing = 0L
                    if (partFile.exists()) partFile.delete()
                }
                if (connection.responseCode !in 200..299) {
                    throw IllegalStateException("HTTP ${connection.responseCode}")
                }

                val responseLength = connection.contentLengthLong.coerceAtLeast(0L)
                val total = if (append) existing + responseLength else responseLength
                connection.inputStream.use { input ->
                    FileOutputStream(partFile, append).use { output ->
                        val buffer = ByteArray(1024 * 1024)
                        var downloaded = existing
                        var lastEmit = 0L
                        while (true) {
                            if (downloadCancelled.get()) {
                                throw InterruptedException("Download cancelled")
                            }
                            val count = input.read(buffer)
                            if (count < 0) break
                            output.write(buffer, 0, count)
                            downloaded += count
                            val now = System.currentTimeMillis()
                            if (now - lastEmit >= 250L) {
                                val percent = if (total > 0) downloaded * 100.0 / total else 0.0
                                emit(DOWNLOAD_PROGRESS, JSONObject()
                                    .put("id", modelId)
                                    .put("filename", safeName)
                                    .put("downloaded", downloaded)
                                    .put("total", total)
                                    .put("percent", percent)
                                    .toString())
                                lastEmit = now
                            }
                        }
                        output.fd.sync()
                    }
                }
                connection.disconnect()

                if (sha256.isNotBlank()) {
                    val actual = sha256(partFile)
                    if (!actual.equals(sha256, true)) {
                        partFile.delete()
                        throw IllegalStateException("SHA-256 mismatch. Expected $sha256, got $actual")
                    }
                }
                if (finalFile.exists()) finalFile.delete()
                if (!partFile.renameTo(finalFile)) {
                    partFile.copyTo(finalFile, overwrite = true)
                    partFile.delete()
                }

                emit(DOWNLOAD_FINISHED, JSONObject()
                    .put("id", modelId)
                    .put("filename", safeName)
                    .put("path", finalFile.absolutePath)
                    .put("size", finalFile.length())
                    .toString())
                emit(MODELS_CHANGED, listLocalModels())
            } catch (error: Throwable) {
                Log.e(TAG, "Download failed", error)
                emit(DOWNLOAD_FAILED, JSONObject()
                    .put("id", modelId)
                    .put("filename", safeName)
                    .put("message", error.message ?: error.javaClass.simpleName)
                    .toString())
            }
        }
    }

    @UsedByGodot
    fun cancelDownload() {
        downloadCancelled.set(true)
    }

    @UsedByGodot
    fun listLocalModels(): String {
        val result = JSONArray()
        modelsDir.listFiles()
            ?.filter { it.isFile && it.extension.equals("gguf", true) }
            ?.sortedBy { it.name.lowercase() }
            ?.forEach {
                result.put(JSONObject()
                    .put("filename", it.name)
                    .put("path", it.absolutePath)
                    .put("size", it.length()))
            }
        return result.toString()
    }

    @UsedByGodot
    fun getModelPath(filename: String): String {
        val file = File(modelsDir, File(filename).name)
        return if (file.isFile) file.absolutePath else ""
    }

    @UsedByGodot
    fun deleteModel(filename: String): Boolean {
        val file = File(modelsDir, File(filename).name)
        val deleted = !file.exists() || file.delete()
        emit(MODELS_CHANGED, listLocalModels())
        return deleted
    }

    @UsedByGodot
    fun loadModel(path: String, contextSize: Int, threads: Int, gpuLayers: Int) {
        inferenceExecutor.execute {
            try {
                val result = JSONObject(nativeLoadModel(path, contextSize, threads, gpuLayers))
                if (result.optBoolean("ok")) {
                    result.put("filename", File(path).name)
                    emit(MODEL_LOADED, result.toString())
                } else {
                    emit(AI_ERROR, result.toString())
                }
            } catch (error: Throwable) {
                emitError("Model load failed", error)
            }
        }
    }

    @UsedByGodot
    fun unloadModel() {
        inferenceExecutor.execute {
            try {
                nativeUnload()
                emit(MODEL_UNLOADED, JSONObject().put("ok", true).toString())
            } catch (error: Throwable) {
                emitError("Model unload failed", error)
            }
        }
    }

    @UsedByGodot
    fun generate(
        prompt: String,
        maxTokens: Int,
        temperature: Float,
        topP: Float,
        topK: Int,
        repeatPenalty: Float
    ) {
        inferenceExecutor.execute {
            try {
                val result = nativeGenerate(
                    prompt,
                    maxTokens,
                    temperature,
                    topP,
                    topK,
                    repeatPenalty
                )
                val json = JSONObject(result)
                if (json.optBoolean("ok")) {
                    emit(GENERATION_FINISHED, json.toString())
                } else {
                    emit(AI_ERROR, json.toString())
                }
            } catch (error: Throwable) {
                emitError("Generation failed", error)
            }
        }
    }

    @UsedByGodot
    fun stopGeneration() {
        nativeStop()
    }

    @UsedByGodot
    fun systemInfo(): String = nativeSystemInfo()

    fun onNativeToken(token: String) {
        emit(TOKEN_RECEIVED, token)
    }

    private fun emit(signal: SignalInfo, payload: String) {
        runOnRenderThread { emitSignal(signal, payload) }
    }

    private fun emitError(prefix: String, error: Throwable) {
        Log.e(TAG, prefix, error)
        emit(AI_ERROR, JSONObject()
            .put("message", "$prefix: ${error.message ?: error.javaClass.simpleName}")
            .toString())
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    override fun onMainDestroy() {
        nativeStop()
        inferenceExecutor.shutdownNow()
        ioExecutor.shutdownNow()
        nativeUnload()
        super.onMainDestroy()
    }

    private external fun nativeLoadModel(path: String, contextSize: Int, threads: Int, gpuLayers: Int): String
    private external fun nativeGenerate(
        prompt: String,
        maxTokens: Int,
        temperature: Float,
        topP: Float,
        topK: Int,
        repeatPenalty: Float
    ): String
    private external fun nativeStop()
    private external fun nativeUnload()
    private external fun nativeSystemInfo(): String
}
