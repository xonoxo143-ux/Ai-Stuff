package com.xonoxo.aiworkbench

import android.content.Context
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

class NativeRuntime(private val context: Context) {
    interface Listener {
        fun onTokenChunk(chunk: String)
        fun onDownloadProgress(payload: JSONObject)
    }

    var listener: Listener? = null

    private val inferenceExecutor = Executors.newSingleThreadExecutor()
    private val ioExecutor = Executors.newSingleThreadExecutor()
    private val downloadCancelled = AtomicBoolean(false)

    private val modelsDir: File by lazy {
        File(context.getExternalFilesDir(null) ?: context.filesDir, "models").apply { mkdirs() }
    }

    companion object {
        init {
            System.loadLibrary("ai_workbench_native")
        }
    }

    fun systemInfo(): String = nativeSystemInfo()

    fun listLocalModels(): JSONArray {
        val result = JSONArray()
        modelsDir.listFiles()
            ?.filter { it.isFile && it.extension.equals("gguf", ignoreCase = true) }
            ?.sortedBy { it.name.lowercase() }
            ?.forEach { file ->
                result.put(
                    JSONObject()
                        .put("filename", file.name)
                        .put("path", file.absolutePath)
                        .put("size", file.length())
                )
            }
        return result
    }

    fun modelPath(filename: String): String {
        val file = File(modelsDir, File(filename).name)
        return if (file.isFile) file.absolutePath else ""
    }

    fun deleteModel(filename: String): Boolean {
        val file = File(modelsDir, File(filename).name)
        return !file.exists() || file.delete()
    }

    fun downloadModel(
        id: String,
        url: String,
        filename: String,
        expectedSha256: String,
        done: (Result<JSONObject>) -> Unit
    ) {
        downloadCancelled.set(false)
        ioExecutor.execute {
            val safeName = File(filename).name
            val finalFile = File(modelsDir, safeName)
            val partFile = File(modelsDir, "$safeName.part")
            try {
                if (finalFile.exists() &&
                    (expectedSha256.isBlank() || sha256(finalFile).equals(expectedSha256, true))) {
                    done(Result.success(
                        JSONObject()
                            .put("id", id)
                            .put("filename", safeName)
                            .put("path", finalFile.absolutePath)
                            .put("cached", true)
                    ))
                    return@execute
                }

                var existing = if (partFile.exists()) partFile.length() else 0L
                val connection = URL(url).openConnection() as HttpURLConnection
                connection.instanceFollowRedirects = true
                connection.connectTimeout = 30_000
                connection.readTimeout = 60_000
                connection.setRequestProperty("User-Agent", "AIWorkbenchKernel/1")
                if (existing > 0L) connection.setRequestProperty("Range", "bytes=$existing-")
                connection.connect()

                val append = existing > 0L &&
                    connection.responseCode == HttpURLConnection.HTTP_PARTIAL
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
                                val percent = if (total > 0L) downloaded * 100.0 / total else 0.0
                                listener?.onDownloadProgress(
                                    JSONObject()
                                        .put("id", id)
                                        .put("filename", safeName)
                                        .put("downloaded", downloaded)
                                        .put("total", total)
                                        .put("percent", percent)
                                )
                                lastEmit = now
                            }
                        }
                        output.fd.sync()
                    }
                }
                connection.disconnect()

                if (expectedSha256.isNotBlank()) {
                    val actual = sha256(partFile)
                    if (!actual.equals(expectedSha256, true)) {
                        partFile.delete()
                        throw IllegalStateException(
                            "SHA-256 mismatch. Expected $expectedSha256, got $actual"
                        )
                    }
                }

                if (finalFile.exists()) finalFile.delete()
                if (!partFile.renameTo(finalFile)) {
                    partFile.copyTo(finalFile, overwrite = true)
                    partFile.delete()
                }

                done(Result.success(
                    JSONObject()
                        .put("id", id)
                        .put("filename", safeName)
                        .put("path", finalFile.absolutePath)
                        .put("size", finalFile.length())
                ))
            } catch (t: Throwable) {
                done(Result.failure(t))
            }
        }
    }

    fun cancelDownload() {
        downloadCancelled.set(true)
    }

    fun loadModel(path: String, contextSize: Int, threads: Int, done: (String) -> Unit) {
        inferenceExecutor.execute {
            done(nativeLoadModel(path, contextSize, threads))
        }
    }

    fun generate(
        prompt: String,
        maxTokens: Int,
        temperature: Float,
        topP: Float,
        topK: Int,
        repeatPenalty: Float,
        done: (String) -> Unit
    ) {
        inferenceExecutor.execute {
            done(nativeGenerate(prompt, maxTokens, temperature, topP, topK, repeatPenalty))
        }
    }

    fun stopGeneration() {
        nativeStop()
    }

    fun unload(done: (() -> Unit)? = null) {
        inferenceExecutor.execute {
            nativeUnload()
            done?.invoke()
        }
    }

    @Suppress("unused")
    fun onNativeTokenChunk(chunk: String) {
        listener?.onTokenChunk(chunk)
    }

    fun shutdown() {
        nativeStop()
        inferenceExecutor.shutdownNow()
        ioExecutor.shutdownNow()
        nativeUnload()
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

    private external fun nativeLoadModel(path: String, contextSize: Int, threads: Int): String
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
