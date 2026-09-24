package com.xonoxo.aiworkbench

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.zip.ZipInputStream

class BundleUpdater(private val context: Context) {
    companion object {
        const val KERNEL_VERSION = 1
        const val REPO = "xonoxo143-ux/Ai-Stuff"
        const val REF = "refs/heads/aistuff"
        const val MANIFEST_URL =
            "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/aistuff/workspace/releases/current.json"
    }

    private val root = File(context.filesDir, "workbench").apply { mkdirs() }
    private val current = File(root, "current").apply { mkdirs() }
    private val prefs = context.getSharedPreferences("ai_workbench_updates", Context.MODE_PRIVATE)

    fun currentDir(): File = current

    fun currentVersion(): Long = prefs.getLong("version", 0L)

    fun hasCurrentBundle(): Boolean = File(current, "index.html").isFile

    fun activeUrl(): String {
        return if (hasCurrentBundle()) {
            "https://appassets.androidplatform.net/current/index.html"
        } else {
            "https://appassets.androidplatform.net/bundled/workbench/index.html"
        }
    }

    fun check(): JSONObject {
        val manifest = fetchJson(MANIFEST_URL)
        validateManifest(manifest)
        return JSONObject()
            .put("local_version", currentVersion())
            .put("remote_version", manifest.getLong("version"))
            .put("update_available", manifest.getLong("version") > currentVersion())
            .put("manifest", manifest)
    }

    fun apply(manifest: JSONObject): JSONObject {
        validateManifest(manifest)
        val version = manifest.getLong("version")
        val url = manifest.getString("bundle_url")
        val expected = manifest.getString("sha256").lowercase()

        val zip = File(root, "staging-$version.zip")
        download(url, zip)

        val actual = sha256(zip)
        if (actual != expected) {
            zip.delete()
            throw IllegalStateException("Bundle SHA-256 mismatch")
        }

        val staging = File(root, "staging-$version")
        staging.deleteRecursively()
        staging.mkdirs()
        unzipSafe(zip, staging)
        zip.delete()

        if (!File(staging, "index.html").isFile) {
            staging.deleteRecursively()
            throw IllegalStateException("Bundle does not contain index.html")
        }

        val backup = File(root, "previous")
        backup.deleteRecursively()
        if (current.exists() && !current.renameTo(backup)) {
            staging.deleteRecursively()
            throw IllegalStateException("Could not stage current bundle for replacement")
        }

        if (!staging.renameTo(current)) {
            current.deleteRecursively()
            if (backup.exists()) backup.renameTo(current)
            staging.deleteRecursively()
            throw IllegalStateException("Could not activate bundle")
        }

        backup.deleteRecursively()
        prefs.edit().putLong("version", version).apply()

        return JSONObject()
            .put("ok", true)
            .put("version", version)
            .put("sha256", actual)
            .put("attestation_url", manifest.optString("attestation_url"))
    }

    private fun validateManifest(manifest: JSONObject) {
        if (manifest.optInt("schema", 0) != 1) {
            throw IllegalStateException("Unsupported update manifest schema")
        }
        if (manifest.optString("source_repo") != REPO) {
            throw IllegalStateException("Unexpected update repository")
        }
        if (manifest.optString("source_ref") != REF) {
            throw IllegalStateException("Unexpected update ref")
        }
        val min = manifest.optInt("kernel_min", Int.MAX_VALUE)
        val max = manifest.optInt("kernel_max", Int.MIN_VALUE)
        if (KERNEL_VERSION !in min..max) {
            throw IllegalStateException(
                "Workbench requires kernel $min..$max; installed kernel is $KERNEL_VERSION"
            )
        }
        val sha = manifest.optString("sha256")
        if (!sha.matches(Regex("^[0-9a-fA-F]{64}$"))) {
            throw IllegalStateException("Update manifest has invalid SHA-256")
        }
        if (!manifest.optString("bundle_url").startsWith("https://raw.githubusercontent.com/")) {
            throw IllegalStateException("Update bundle URL is not an approved GitHub raw URL")
        }
    }

    private fun fetchJson(url: String): JSONObject {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 20_000
        connection.readTimeout = 30_000
        connection.setRequestProperty("User-Agent", "AIWorkbenchKernel/1")
        val code = connection.responseCode
        val body = (if (code in 200..299) connection.inputStream else connection.errorStream)
            ?.bufferedReader()
            ?.use { it.readText() }
            .orEmpty()
        connection.disconnect()
        if (code !in 200..299) throw IllegalStateException("Update HTTP $code")
        return JSONObject(body)
    }

    private fun download(url: String, target: File) {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = 20_000
        connection.readTimeout = 60_000
        connection.setRequestProperty("User-Agent", "AIWorkbenchKernel/1")
        val code = connection.responseCode
        if (code !in 200..299) {
            connection.disconnect()
            throw IllegalStateException("Bundle HTTP $code")
        }
        connection.inputStream.use { input ->
            FileOutputStream(target).use { output ->
                input.copyTo(output)
                output.fd.sync()
            }
        }
        connection.disconnect()
    }

    private fun unzipSafe(zip: File, destination: File) {
        val rootCanonical = destination.canonicalFile
        ZipInputStream(FileInputStream(zip)).use { input ->
            while (true) {
                val entry = input.nextEntry ?: break
                val out = File(destination, entry.name).canonicalFile
                if (!out.path.startsWith(rootCanonical.path + File.separator)) {
                    throw IllegalStateException("Rejected unsafe zip entry")
                }
                if (entry.isDirectory) {
                    out.mkdirs()
                } else {
                    out.parentFile?.mkdirs()
                    FileOutputStream(out).use { output -> input.copyTo(output) }
                }
                input.closeEntry()
            }
        }
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
}
