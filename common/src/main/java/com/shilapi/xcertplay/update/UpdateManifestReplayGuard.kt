package com.shilapi.xcertplay.update

import android.content.Context

/**
 * Remembers the newest signed payload accepted per channel. Replaying an older feed after a newer
 * one was accepted is rejected; re-fetching the exact same signed payload remains idempotent.
 * Android app-data clearing/reinstall resets this local checkpoint, so this is not a hardware
 * monotonic counter. Installed APK version/signer checks remain the independent anti-downgrade
 * boundary.
 */
internal object UpdateManifestReplayGuard {
    private const val PREFERENCES = "carpaly_ota_replay_guard"
    private val lock = Any()

    internal fun accept(context: Context, channel: UpdateChannel, candidate: VerifiedUpdateManifest) {
        val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
        val prefix = channel.name.lowercase()
        val timestampKey = "$prefix.issuedAt"
        val digestKey = "$prefix.payloadSha256"
        synchronized(lock) {
            val previousTimestamp = preferences.getLong(timestampKey, -1L)
            val previousDigest = preferences.getString(digestKey, null)
            when {
                candidate.issuedAtMillis < previousTimestamp ->
                    throw UpdateManifestException("OTA manifest replayed an older signed feed")
                candidate.issuedAtMillis == previousTimestamp && previousDigest != candidate.payloadSha256 ->
                    throw UpdateManifestException("OTA manifest reused an issued time for different signed content")
                candidate.issuedAtMillis > previousTimestamp -> {
                    val stored = preferences.edit()
                        .putLong(timestampKey, candidate.issuedAtMillis)
                        .putString(digestKey, candidate.payloadSha256)
                        .commit()
                    if (!stored) throw UpdateManifestException("Could not persist OTA replay protection state")
                }
            }
        }
    }
}
