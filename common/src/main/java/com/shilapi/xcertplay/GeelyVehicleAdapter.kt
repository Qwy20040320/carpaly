package com.shilapi.xcertplay

import android.content.Context
import android.os.Build

/**
 * Read-only identification for Geely Xingyue L (KX11) head units.
 *
 * This adapter deliberately has no CAN, UDS, Vehicle HAL or vendor Binder writes. A third-party
 * application cannot safely infer those interfaces from a model name, and a detection result is
 * never evidence that a profile has passed a real-vehicle test.
 */
enum class GeelyKx11Profile(val key: String) {
    KX11_2021("kx11_2021"),
    KX11_2022("kx11_2022"),
    KX11_2023("kx11_2023"),
    KX11_2024("kx11_2024"),
    KX11_2024_TIANJI("kx11_2024_tianji"),
    KX11_2025("kx11_2025"),
    KX11_2026("kx11_2026"),
    KX11_GENERIC("kx11_generic");

    companion object {
        fun fromKey(key: String?): GeelyKx11Profile? = entries.firstOrNull { it.key == key }
    }
}

enum class GeelyDetectionConfidence { NOT_DETECTED, POSSIBLE, IDENTIFIED }

data class GeelyVehicleEvidence(
    val manufacturer: String?,
    val brand: String?,
    val product: String?,
    val model: String?,
    val fingerprint: String?,
    val display: String?,
    val androidApi: Int,
)

data class GeelyVehicleDetection(
    val profile: GeelyKx11Profile?,
    val confidence: GeelyDetectionConfidence,
    /** Stable, user-visible reasons suitable for a diagnostic report; never contains a vehicle identifier. */
    val evidence: List<String>,
)

/**
 * Resolves a KX11 profile from explicit build identity only.  A 1920 x 720 display is recorded by
 * the host separately, but never selects a model because that resolution is shared by other cars.
 */
object GeelyVehicleAdapter {
    private const val PREFS = "diplay"
    private const val KEY_MANUAL_PROFILE = "geely_kx11_manual_profile"

    fun manualProfile(context: Context): GeelyKx11Profile? =
        GeelyKx11Profile.fromKey(
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_MANUAL_PROFILE, null),
        )

    /** A null profile restores automatic detection; all listed profiles remain candidates until road-tested. */
    fun saveManualProfile(context: Context, profile: GeelyKx11Profile?) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply {
            if (profile == null) remove(KEY_MANUAL_PROFILE) else putString(KEY_MANUAL_PROFILE, profile.key)
        }.apply()
    }

    fun label(profile: GeelyKx11Profile): String = when (profile) {
        GeelyKx11Profile.KX11_2021 -> "KX11 2021"
        GeelyKx11Profile.KX11_2022 -> "KX11 2022"
        GeelyKx11Profile.KX11_2023 -> "KX11 2023"
        GeelyKx11Profile.KX11_2024 -> "KX11 2024"
        GeelyKx11Profile.KX11_2024_TIANJI -> "KX11 2024 天际版"
        GeelyKx11Profile.KX11_2025 -> "KX11 2025"
        GeelyKx11Profile.KX11_2026 -> "KX11 2026"
        GeelyKx11Profile.KX11_GENERIC -> "KX11 Generic"
    }

    fun detect(evidence: GeelyVehicleEvidence): GeelyVehicleDetection {
        val values = listOf(
            "manufacturer" to evidence.manufacturer,
            "brand" to evidence.brand,
            "product" to evidence.product,
            "model" to evidence.model,
            "fingerprint" to evidence.fingerprint,
            "display" to evidence.display,
        )
        val joined = values.mapNotNull { (_, value) -> value?.lowercase() }.joinToString(" ")
        val geelyEvidence = values.filter { (_, value) ->
            value?.contains("geely", ignoreCase = true) == true ||
                value?.contains("ecarx", ignoreCase = true) == true ||
                value?.contains("ecar x", ignoreCase = true) == true
        }.map { (field, _) -> field }
        val kx11Evidence = values.filter { (_, value) ->
            value?.contains("kx11", ignoreCase = true) == true ||
                value?.contains("xingyue", ignoreCase = true) == true ||
                value?.contains("monjaro", ignoreCase = true) == true
        }.map { (field, _) -> field }
        val reason = buildList {
            if (geelyEvidence.isNotEmpty()) add("Geely platform identity: ${geelyEvidence.joinToString()}")
            if (kx11Evidence.isNotEmpty()) add("KX11 model identity: ${kx11Evidence.joinToString()}")
            add("Android API ${evidence.androidApi}")
        }
        if (geelyEvidence.isEmpty() && kx11Evidence.isEmpty()) {
            return GeelyVehicleDetection(null, GeelyDetectionConfidence.NOT_DETECTED, reason)
        }
        if (geelyEvidence.isEmpty() || kx11Evidence.isEmpty()) {
            return GeelyVehicleDetection(null, GeelyDetectionConfidence.POSSIBLE, reason)
        }
        val profile = yearProfile(joined)
        return GeelyVehicleDetection(profile ?: GeelyKx11Profile.KX11_GENERIC,
            GeelyDetectionConfidence.IDENTIFIED, reason)
    }

    fun currentBuild(): GeelyVehicleDetection = detect(
        GeelyVehicleEvidence(
            manufacturer = Build.MANUFACTURER,
            brand = Build.BRAND,
            product = Build.PRODUCT,
            model = Build.MODEL,
            fingerprint = Build.FINGERPRINT,
            display = Build.DISPLAY,
            androidApi = Build.VERSION.SDK_INT,
        ),
    )

    private fun yearProfile(joined: String): GeelyKx11Profile? = when {
        "tianji" in joined || "天际" in joined -> GeelyKx11Profile.KX11_2024_TIANJI
        "2021" in joined -> GeelyKx11Profile.KX11_2021
        "2022" in joined -> GeelyKx11Profile.KX11_2022
        "2023" in joined -> GeelyKx11Profile.KX11_2023
        "2024" in joined -> GeelyKx11Profile.KX11_2024
        "2025" in joined -> GeelyKx11Profile.KX11_2025
        "2026" in joined -> GeelyKx11Profile.KX11_2026
        else -> null
    }
}
