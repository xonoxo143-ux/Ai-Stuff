package com.xonoxo.aiworkbench

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class SecureStore(context: Context) {
    private val prefs = context.getSharedPreferences("ai_workbench_secure", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_ALIAS = "ai_workbench_kernel_aes_v1"
    }

    fun put(name: String, value: String) {
        if (value.isBlank()) {
            delete(name)
            return
        }
        prefs.edit().putString(name, encrypt(value)).apply()
    }

    fun get(name: String): String {
        val stored = prefs.getString(name, null) ?: return ""
        return decrypt(stored)
    }

    fun delete(name: String) {
        prefs.edit().remove(name).apply()
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val existing = keyStore.getKey(KEY_ALIAS, null)
        if (existing is SecretKey) return existing

        val generator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            "AndroidKeyStore"
        )
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        return generator.generateKey()
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val iv = Base64.encodeToString(cipher.iv, Base64.NO_WRAP)
        val payload = Base64.encodeToString(
            cipher.doFinal(value.toByteArray(Charsets.UTF_8)),
            Base64.NO_WRAP
        )
        return "$iv:$payload"
    }

    private fun decrypt(stored: String): String {
        val split = stored.indexOf(':')
        require(split > 0) { "Invalid encrypted value" }
        val iv = Base64.decode(stored.substring(0, split), Base64.NO_WRAP)
        val payload = Base64.decode(stored.substring(split + 1), Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(
            Cipher.DECRYPT_MODE,
            getOrCreateKey(),
            GCMParameterSpec(128, iv)
        )
        return String(cipher.doFinal(payload), Charsets.UTF_8)
    }
}
