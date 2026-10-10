package com.shilapi.xcertplay

import android.content.Context
import android.os.Build

/**
 * A conservative, display-only head-unit profile.
 *
 * Profiles never access a vehicle bus, send ADB commands, or assume an OEM app package. They only
 * describe the CarPlay receiver running in this app's own Android window. That distinction is
 * important for production cars such as Xingyue L, whose Galaxy OS vehicle APIs vary by OTA version.
 */
enum class HeadUnitProfile(val key: String) {
    /** Use the build identity when it is recognisable; otherwise leave generic defaults alone. */
    AUTOMATIC("automatic"),
    /** Do not apply any vehicle-specific receiver defaults. */
    GENERIC("generic"),
    /** Geely Xingyue L / KX11 / Monjaro Galaxy OS receiver profile. */
    GEELY_XINGYUE_L("geely_xingyue_l");

    companion object {
        private const val PREFS = "diplay"
        private const val KEY = "head_unit_profile"

        fun fromKey(key: String?): HeadUnitProfile? = entries.firstOrNull { it.key == key }

        fun selected(context: Context): HeadUnitProfile =
            fromKey(context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null))
                ?: AUTOMATIC

        fun save(context: Context, profile: HeadUnitProfile) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, profile.key).apply()
        }

        /** Testable build-identity detector; screen size alone is never evidence of a car model. */
        fun detect(
            manufacturer: String?,
            brand: String?,
            product: String?,
            model: String?,
            fingerprint: String?,
            display: String?,
        ): HeadUnitProfile? {
            val detection = GeelyVehicleAdapter.detect(GeelyVehicleEvidence(
                manufacturer, brand, product, model, fingerprint, display, Build.VERSION.SDK_INT,
            ))
            return GEELY_XINGYUE_L.takeIf { detection.confidence == GeelyDetectionConfidence.IDENTIFIED }
        }

        fun detected(): HeadUnitProfile? = detect(
            manufacturer = Build.MANUFACTURER,
            brand = Build.BRAND,
            product = Build.PRODUCT,
            model = Build.MODEL,
            fingerprint = Build.FINGERPRINT,
            display = Build.DISPLAY,
        )

        fun active(context: Context): HeadUnitProfile? {
            if (GeelyVehicleAdapter.manualProfile(context) != null) return GEELY_XINGYUE_L
            return when (val profile = selected(context)) {
                AUTOMATIC -> detected()
                GENERIC -> null
                else -> profile
            }
        }
    }
}

/** Receiver defaults verified against Xingyue L's published 1920 x 720, 12.3-inch centre display. */
internal object GeelyXingyueLProfile {
    const val VIEWPORT_WIDTH = 1920
    const val VIEWPORT_HEIGHT = 720
    const val CARPLAY_MANUFACTURER = "Geely"
    const val CARPLAY_MODEL = "Xingyue L"
    const val CARPLAY_OEM_LABEL = "Geely"

    /** The app must use its actual window dimensions; the profile must never fabricate a 1920 x 720 surface. */
    fun matchesViewport(width: Int, height: Int): Boolean =
        width == VIEWPORT_WIDTH && height == VIEWPORT_HEIGHT
}

/** Preserve the upstream vehicle icon except when a Geely receiver profile is actually selected. */
internal object CarPlayVehicleBranding {
    fun usesGeelyIcon(profile: HeadUnitProfile?): Boolean =
        profile == HeadUnitProfile.GEELY_XINGYUE_L
}
