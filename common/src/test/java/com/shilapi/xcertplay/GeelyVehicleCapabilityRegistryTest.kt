package com.shilapi.xcertplay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GeelyVehicleCapabilityRegistryTest {
    @Test fun noSelectedGeelyProfileKeepsVehicleCapabilitiesNotApplicable() {
        val snapshot = GeelyVehicleCapabilityRegistry.evaluate(
            profile = null,
            oneOsPermission = GeelyPermissionObservation.GRANTED,
            climatePermission = GeelyPermissionObservation.GRANTED,
            presentationDisplayCount = 0,
        )

        assertNull(snapshot.profileKey)
        assertEquals(GeelyCapabilityState.PROFILE_NOT_SELECTED, snapshot.finding(GeelyCapability.STEERING_WHEEL_INPUT).state)
        assertEquals(GeelyCapabilityState.PROFILE_NOT_SELECTED, snapshot.finding(GeelyCapability.HUD_NAVIGATION).state)
        assertEquals(GeelyCapabilityState.DISABLED_NO_AUTHORIZED_WRITE_API, snapshot.finding(GeelyCapability.VEHICLE_CONTROL).state)
    }

    @Test fun unrequestedOrDeniedOemPermissionsNeverEnableAnAdapter() {
        val notRequested = GeelyVehicleCapabilityRegistry.evaluate(
            GeelyKx11Profile.KX11_2024_TIANJI,
            GeelyPermissionObservation.NOT_REQUESTED,
            GeelyPermissionObservation.NOT_REQUESTED,
            presentationDisplayCount = null,
        )
        val denied = GeelyVehicleCapabilityRegistry.evaluate(
            GeelyKx11Profile.KX11_2024_TIANJI,
            GeelyPermissionObservation.DENIED,
            GeelyPermissionObservation.DENIED,
            presentationDisplayCount = null,
        )

        assertEquals(GeelyCapabilityState.PERMISSION_NOT_REQUESTED,
            notRequested.finding(GeelyCapability.STEERING_WHEEL_INPUT).state)
        assertEquals(GeelyCapabilityState.PERMISSION_NOT_REQUESTED,
            notRequested.finding(GeelyCapability.CLIMATE_STATUS).state)
        assertEquals(GeelyCapabilityState.PERMISSION_DENIED,
            denied.finding(GeelyCapability.STEERING_WHEEL_INPUT).state)
        assertEquals(GeelyCapabilityState.PERMISSION_DENIED,
            denied.finding(GeelyCapability.CLIMATE_STATUS).state)
    }

    @Test fun grantedPermissionIsStillOnlyStaticEvidenceUntilServiceContractIsVerified() {
        val snapshot = GeelyVehicleCapabilityRegistry.evaluate(
            GeelyKx11Profile.KX11_2024_TIANJI,
            GeelyPermissionObservation.GRANTED,
            GeelyPermissionObservation.GRANTED,
            presentationDisplayCount = 0,
        )

        assertEquals(GeelyCapabilityState.STATIC_EVIDENCE_ONLY,
            snapshot.finding(GeelyCapability.STEERING_WHEEL_INPUT).state)
        assertEquals(GeelyCapabilityState.STATIC_EVIDENCE_ONLY,
            snapshot.finding(GeelyCapability.CLIMATE_STATUS).state)
        assertEquals(GeelyCapabilityState.DISABLED_NO_AUTHORIZED_WRITE_API,
            snapshot.finding(GeelyCapability.VEHICLE_CONTROL).state)
    }

    @Test fun presentationDisplayIsNotReportedAsOemCarplayOutput() {
        val snapshot = GeelyVehicleCapabilityRegistry.evaluate(
            GeelyKx11Profile.KX11_2024,
            GeelyPermissionObservation.DENIED,
            GeelyPermissionObservation.NOT_REQUESTED,
            presentationDisplayCount = 2,
        )
        val display = snapshot.finding(GeelyCapability.MULTI_DISPLAY)

        assertEquals(GeelyCapabilityState.ANDROID_PRESENTATION_DISPLAY_FOUND, display.state)
        assertTrue(display.evidence.contains("not established"))
    }

    @Test fun reportExplicitlyStatesNoOemOrVehicleWritesWereAttempted() {
        val report = GeelyVehicleCapabilityRegistry.evaluate(
            GeelyKx11Profile.KX11_GENERIC,
            GeelyPermissionObservation.NOT_REQUESTED,
            GeelyPermissionObservation.NOT_REQUESTED,
            presentationDisplayCount = null,
        ).asDiagnosticText()

        assertTrue(report.contains("No OEM Binder"))
        assertTrue(report.contains("VEHICLE_CONTROL=DISABLED_NO_AUTHORIZED_WRITE_API"))
    }

    @Test fun oneOsProbeDistinguishesMissingPermissionFromStaticVisibility() {
        val profile = GeelyKx11Profile.KX11_2024_TIANJI_A2
        val missing = GeelyVehicleCapabilityRegistry.evaluate(
            profile = profile,
            oneOsPermission = GeelyPermissionObservation.NOT_REQUESTED,
            climatePermission = GeelyPermissionObservation.NOT_REQUESTED,
            presentationDisplayCount = null,
            oneOsInputService = GeelyInputServiceProbeResult(GeelyInputServiceProbeState.NOT_FOUND),
        )
        val permissionRequired = GeelyVehicleCapabilityRegistry.evaluate(
            profile = profile,
            oneOsPermission = GeelyPermissionObservation.NOT_REQUESTED,
            climatePermission = GeelyPermissionObservation.NOT_REQUESTED,
            presentationDisplayCount = null,
            oneOsInputService = GeelyInputServiceProbeResult(
                GeelyInputServiceProbeState.PERMISSION_REQUIRED,
                "geely.oneos.permission.SERVICE",
            ),
        )
        val visibleOnly = GeelyVehicleCapabilityRegistry.evaluate(
            profile = profile,
            oneOsPermission = GeelyPermissionObservation.NOT_REQUESTED,
            climatePermission = GeelyPermissionObservation.NOT_REQUESTED,
            presentationDisplayCount = null,
            oneOsInputService = GeelyInputServiceProbeResult(GeelyInputServiceProbeState.STATIC_EVIDENCE_ONLY),
        )

        assertEquals(GeelyCapabilityState.OEM_SERVICE_NOT_FOUND,
            missing.finding(GeelyCapability.ONEOS_INPUT_SERVICE).state)
        assertEquals(GeelyCapabilityState.OEM_SERVICE_PERMISSION_REQUIRED,
            permissionRequired.finding(GeelyCapability.ONEOS_INPUT_SERVICE).state)
        assertEquals(GeelyCapabilityState.STATIC_EVIDENCE_ONLY,
            visibleOnly.finding(GeelyCapability.ONEOS_INPUT_SERVICE).state)
        assertTrue(visibleOnly.finding(GeelyCapability.ONEOS_INPUT_SERVICE).evidence.contains("no service binding"))
    }

    private fun GeelyCapabilitySnapshot.finding(capability: GeelyCapability) =
        findings.first { it.capability == capability }
}
