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

    private fun GeelyCapabilitySnapshot.finding(capability: GeelyCapability) =
        findings.first { it.capability == capability }
}
