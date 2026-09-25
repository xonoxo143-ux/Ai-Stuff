package com.xonoxo.aiworkbench

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class NativeAppUpdater(private val context: Context) {
    companion object {
        const val MANIFEST_URL =
            "https://raw.githubusercontent.com/xonoxo143-ux/Ai-Stuff/aistuff/workspace/releases/native/current.json"
        const val PACKAGE_NAME = "com.xonoxo.aiworkbench.k2"
        const val SIGNING_SHA256 =
            "E2E3D6D0FE17D97FE76855F5758D923DBA2A5F7D95EA59DA257B38B042C907EF"
    }

    private val updateDir = File(context.cacheDir, "updates").apply { mkdirs() }

    fun check(): JSONObject {
        val manifest = fetchJson(cacheBust(MANIFEST_URL, "manifest"))
        validateManifest(manifest)

        val installedInfo = context.packageManager
            .getPackageInfo(context.packageName, 0)
        val installedVersion = installedInfo.longVersionCode
        val remoteVersion = manifest.getLong("version_code")

        return JSONObject()
            .put("installed_version_code", installedVersion)
            .put("installed_version_name", installedInfo.versionName.orEmpty())
            .put("remote_version_code", remoteVersion)
            .put("remote_version_name", manifest.optString("version_name"))
            .put("update_available", remoteVersion > installedVersion)
            .put("can_install_packages", canRequestInstalls())
            .put("manifest", manifest)
    }

    fun canRequestInstalls(): Boolean =
        context.packageManager.canRequestPackageInstalls()

    fun openInstallPermissionSettings() {
        val intent = Intent(
            Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse("package:${context.packageName}")
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    fun downloadAndVerify(manifest: JSONObject): JSONObject {
        validateManifest(manifest)

        val installedVersion = context.packageManager
            .getPackageInfo(context.packageName, 0)
            .longVersionCode
        val remoteVersion = manifest.getLong("version_code")
        require(remoteVersion > installedVersion) {
            "Native update is not newer than the installed app"
        }

        val target = File(updateDir, "AIWorkbench-$remoteVersion.apk")
        download(cacheBust(manifest.getString("apk_url"), remoteVersion.toString()), target)

        val expectedSha = manifest.getString("sha256").lowercase()
        val actualSha = sha256(target)
        require(actualSha == expectedSha) {
            target.delete()
            "Native APK SHA-256 mismatch"
        }

        val info = context.packageManager.getPackageArchiveInfo(
            target.absolutePath,
            PackageManager.GET_SIGNING_CERTIFICATES
        ) ?: run {
            target.delete()
            throw IllegalStateException("Downloaded file is not a valid Android APK")
        }

        require(info.packageName == PACKAGE_NAME) {
            target.delete()
            "Unexpected APK package: ${info.packageName}"
        }
        require(info.longVersionCode == remoteVersion) {
            target.delete()
            "APK version does not match update manifest"
        }

        val signer = info.signingInfo
            ?.apkContentsSigners
            ?.firstOrNull()
            ?: run {
                target.delete()
                throw IllegalStateException("APK has no signing certificate")
            }
        val signerSha = sha256(signer.toByteArray()).uppercase()
        require(signerSha == SIGNING_SHA256) {
            target.delete()
            "APK signing certificate is not the pinned AI Workbench identity"
        }

        return JSONObject()
            .put("path", target.absolutePath)
            .put("version_code", remoteVersion)
            .put("sha256", actualSha)
            .put("signing_sha256", signerSha)
    }

    fun launchInstaller(apkPath: String) {
        require(canRequestInstalls()) {
            "Install permission is not enabled for AI Workbench"
        }

        val apk = File(apkPath)
        require(
            apk.isFile &&
                apk.canonicalPath.startsWith(updateDir.canonicalPath + File.separator)
        ) {
            "Invalid update APK path"
        }

        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.files",
            apk
        )

        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

        context.startActivity(intent)
    }

    private fun validateManifest(manifest: JSONObject) {
        require(manifest.optInt("schema", 0) == 1) {
            "Unsupported native update manifest schema"
        }
        require(manifest.optString("package") == PACKAGE_NAME) {
            "Native update targets a different package"
        }
        require(
            normalizeFingerprint(manifest.optString("signing_sha256")) ==
                SIGNING_SHA256
        ) {
            "Native update manifest has an unexpected signing identity"
        }
        require(manifest.optLong("version_code", 0L) > 0L) {
            "Native update manifest has invalid version code"
        }
        require(manifest.optString("sha256").matches(Regex("^[0-9a-fA-F]{64}$"))) {
            "Native update manifest has invalid SHA-256"
        }
        require(manifest.optString("apk_url").startsWith("https://github.com/")) {
            "Native APK URL is not an approved GitHub release URL"
        }
    }

    private fun normalizeFingerprint(value: String): String =
        value.filter { it.isLetterOrDigit() }.uppercase()

    private fun cacheBust(url: String, tag: String): String {
        val separator = if (url.contains("?")) "&" else "?"
        return "$url${separator}v=$tag&ts=${System.currentTimeMillis()}"
    }

    private fun fetchJson(url: String): JSONObject {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.useCaches = false
        connection.connectTimeout = 20_000
        connection.readTimeout = 30_000
        connection.setRequestProperty("User-Agent", "AIWorkbenchKernel/2")
        connection.setRequestProperty("Cache-Control", "no-cache, no-store")
        connection.setRequestProperty("Pragma", "no-cache")

        val code = connection.responseCode
        val body = (if (code in 200..299) connection.inputStream else connection.errorStream)
            ?.bufferedReader()
            ?.use { it.readText() }
            .orEmpty()
        connection.disconnect()

        if (code !in 200..299) {
            throw IllegalStateException("Native update HTTP $code")
        }
        return JSONObject(body)
    }

    private fun download(url: String, target: File) {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.instanceFollowRedirects = true
        connection.useCaches = false
        connection.connectTimeout = 20_000
        connection.readTimeout = 120_000
        connection.setRequestProperty("User-Agent", "AIWorkbenchKernel/2")
        connection.setRequestProperty("Cache-Control", "no-cache, no-store")
        connection.setRequestProperty("Pragma", "no-cache")

        val code = connection.responseCode
        if (code !in 200..299) {
            val location = connection.getHeaderField("Location")
            connection.disconnect()
            if (code in 300..399 && !location.isNullOrBlank()) {
                download(location, target)
                return
            }
            throw IllegalStateException("Native APK HTTP $code")
        }

        connection.inputStream.use { input ->
            FileOutputStream(target).use { output ->
                input.copyTo(output)
                output.fd.sync()
            }
        }
        connection.disconnect()
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

    private fun sha256(bytes: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
        return digest.joinToString("") { "%02x".format(it) }
    }
}
