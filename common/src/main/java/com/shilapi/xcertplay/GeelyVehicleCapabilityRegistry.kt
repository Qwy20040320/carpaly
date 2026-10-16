package com.shilapi.xcertplay

import android.content.Context
import android.content.pm.PackageManager
import android.hardware.display.DisplayManager

/** A permission observation is kept separate from service/API availability. */
internal enum class GeelyPermissionObservation {
    NOT_REQUESTED,
    DENIED,
    GRANTED,
}

internal enum class GeelyCapabilityState {
    PROFILE_NOT_SELECTED,
    PERMISSION_NOT_REQUESTED,
    PERMISSION_DENIED,
    STATIC_EVIDENCE_ONLY,
    ANDROID_PRESENTATION_DISPLAY_FOUND,
    NO_PRESENTATION_DISPLAY,
    DISPLAY_QUERY_UNAVAILABLE,
    DISABLED_NO_AUTHORIZED_WRITE_API,
}

internal enum class GeelyCapability {
    STEERING_WHEEL_INPUT,
    VEHICLE_SENSORS,
    FUEL_LEVEL,
    HUD_NAVIGATION,
    INSTRUMENT_CLUSTER_NAVIGATION,
    HUD_LYRICS,
    MULTI_DISPLAY,
    CLIMATE_STATUS,
    VEHICLE_CONTROL,
}

internal data class GeelyCapabilityFinding(
    val capability: GeelyCapability,
    val state: GeelyCapabilityState,
    val evidence: String,
)

internal data class GeelyCapabilitySnapshot(
    val profileKey: String?,
    val findings: List<GeelyCapabilityFinding>,
) {
    fun asDiagnosticText(): String = buildString {
        appendLine("profile=${profileKey ?: "not-selected"}")
        findings.forEach { finding ->
            appendLine("${finding.capability.name}=${finding.state.name}; ${finding.evidence}")
        }
        append("No OEM Binder, broadcast, CAN, UDS, climate, display or vehicle-control write was attempted.")
    }
}

/**
 * Conservative capability discovery. Package/permission/display observations are diagnostics,
 * not proof that an OEM service is callable or that a vehicle feature works.
 */
internal object GeelyVehicleCapabilityRegistry {
    const val ONEOS_SERVICE_PERMISSION = "geely.oneos.permission.SERVICE"
    const val CAR_CLIMATE_CONTROL_PERMISSION = "android.car.permission.CONTROL_CAR_CLIMATE"

    fun inspect(context: Context): GeelyCapabilitySnapshot {
        val selectedGeely = HeadUnitProfile.active(context) == HeadUnitProfile.GEELY_XINGYUE_L
        val profile = if (!selectedGeely) null else {
            GeelyVehicleAdapter.manualProfile(context)
                ?: GeelyVehicleAdapter.currentBuild().profile
                ?: GeelyKx11Profile.KX11_GENERIC
        }
        val displayCount = runCatching {
            context.getSystemService(DisplayManager::class.java)
                ?.getDisplays(DisplayManager.DISPLAY_CATEGORY_PRESENTATION)
                ?.size
        }.getOrNull()
        return evaluate(
            profile = profile,
            oneOsPermission = permissionObservation(context, ONEOS_SERVICE_PERMISSION),
            climatePermission = permissionObservation(context, CAR_CLIMATE_CONTROL_PERMISSION),
            presentationDisplayCount = displayCount,
        )
    }

    /** Pure evaluator used by tests. A granted permission still does not imply a working OEM API. */
    fun evaluate(
        profile: GeelyKx11Profile?,
        oneOsPermission: GeelyPermissionObservation,
        climatePermission: GeelyPermissionObservation,
        presentationDisplayCount: Int?,
    ): GeelyCapabilitySnapshot {
        val steeringState = when {
            profile == null -> GeelyCapabilityState.PROFILE_NOT_SELECTED
            oneOsPermission == GeelyPermissionObservation.NOT_REQUESTED -> GeelyCapabilityState.PERMISSION_NOT_REQUESTED
            oneOsPermission == GeelyPermissionObservation.DENIED -> GeelyCapabilityState.PERMISSION_DENIED
            else -> GeelyCapabilityState.STATIC_EVIDENCE_ONLY
        }
        val steeringEvidence = when (steeringState) {
            GeelyCapabilityState.PERMISSION_NOT_REQUESTED -> "$ONEOS_SERVICE_PERMISSION is not requested by this app"
            GeelyCapabilityState.PERMISSION_DENIED -> "$ONEOS_SERVICE_PERMISSION is not granted; OEM listener is not connected"
            GeelyCapabilityState.STATIC_EVIDENCE_ONLY -> "permission observed granted, but service/API and key semantics remain unverified"
            else -> "select a KX11 profile before considering the OneOS evidence"
        }
        val climateState = when {
            profile == null -> GeelyCapabilityState.PROFILE_NOT_SELECTED
            climatePermission == GeelyPermissionObservation.NOT_REQUESTED -> GeelyCapabilityState.PERMISSION_NOT_REQUESTED
            climatePermission == GeelyPermissionObservation.DENIED -> GeelyCapabilityState.PERMISSION_DENIED
            else -> GeelyCapabilityState.STATIC_EVIDENCE_ONLY
        }
        val climateEvidence = when (climateState) {
            GeelyCapabilityState.PERMISSION_NOT_REQUESTED -> "$CAR_CLIMATE_CONTROL_PERMISSION is not requested by this app"
            GeelyCapabilityState.PERMISSION_DENIED -> "$CAR_CLIMATE_CONTROL_PERMISSION is not granted; climate access is disabled"
            GeelyCapabilityState.STATIC_EVIDENCE_ONLY -> "permission observed granted, but no authorized read API or units are verified"
            else -> "select a KX11 profile before considering the climate evidence"
        }
        val displayState = when (presentationDisplayCount) {
            null -> GeelyCapabilityState.DISPLAY_QUERY_UNAVAILABLE
            0 -> GeelyCapabilityState.NO_PRESENTATION_DISPLAY
            else -> GeelyCapabilityState.ANDROID_PRESENTATION_DISPLAY_FOUND
        }
        val displayEvidence = when (displayState) {
            GeelyCapabilityState.ANDROID_PRESENTATION_DISPLAY_FOUND ->
                "Android Presentation API reports $presentationDisplayCount display(s); physical/OEM CarPlay routing is not established"
            GeelyCapabilityState.NO_PRESENTATION_DISPLAY -> "Android Presentation API reports no presentation display"
            else -> "Android Presentation display query was unavailable"
        }
        val profileState = if (profile == null) GeelyCapabilityState.PROFILE_NOT_SELECTED
            else GeelyCapabilityState.STATIC_EVIDENCE_ONLY
        val staticEvidence = if (profile == null) "select a KX11 profile for this capability report"
            else "third-party APK evidence only; current service and permission grant are not verified"

        return GeelyCapabilitySnapshot(
            profileKey = profile?.key,
            findings = listOf(
                GeelyCapabilityFinding(GeelyCapability.STEERING_WHEEL_INPUT, steeringState, steeringEvidence),
                GeelyCapabilityFinding(GeelyCapability.VEHICLE_SENSORS, profileState, staticEvidence),
                GeelyCapabilityFinding(GeelyCapability.FUEL_LEVEL, profileState, staticEvidence),
                GeelyCapabilityFinding(GeelyCapability.HUD_NAVIGATION, profileState, staticEvidence),
                GeelyCapabilityFinding(GeelyCapability.INSTRUMENT_CLUSTER_NAVIGATION, profileState, staticEvidence),
                GeelyCapabilityFinding(GeelyCapability.HUD_LYRICS, profileState, staticEvidence),
                GeelyCapabilityFinding(GeelyCapability.MULTI_DISPLAY, displayState, displayEvidence),
                GeelyCapabilityFinding(GeelyCapability.CLIMATE_STATUS, climateState, climateEvidence),
                GeelyCapabilityFinding(
                    GeelyCapability.VEHICLE_CONTROL,
                    GeelyCapabilityState.DISABLED_NO_AUTHORIZED_WRITE_API,
                    "all unverified vehicle write/control operations remain disabled",
                ),
            ),
        )
    }

    private fun permissionObservation(context: Context, permission: String): GeelyPermissionObservation {
        val requested = runCatching {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageInfo(context.packageName, PackageManager.GET_PERMISSIONS)
                .requestedPermissions
                ?.contains(permission) == true
        }.getOrDefault(false)
        val granted = runCatching { context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED }
            .getOrDefault(false)
        return when {
            granted -> GeelyPermissionObservation.GRANTED
            requested -> GeelyPermissionObservation.DENIED
            else -> GeelyPermissionObservation.NOT_REQUESTED
        }
    }
}
