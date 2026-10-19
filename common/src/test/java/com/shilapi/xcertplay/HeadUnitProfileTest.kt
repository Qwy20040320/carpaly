package com.shilapi.xcertplay

import com.shilapi.xcertplay.host.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HeadUnitProfileTest {
    @Test fun `recognises Xingyue L only when Geely identity and model evidence agree`() {
        assertEquals(HeadUnitProfile.GEELY_XINGYUE_L, HeadUnitProfile.detect(
            manufacturer = "ECARX", brand = "Geely", product = "KX11", model = "Xingyue L",
            fingerprint = "geely/kx11/user", display = "Galaxy OS",
        ))
        assertNull(HeadUnitProfile.detect(
            manufacturer = "Geely", brand = "Geely", product = "generic", model = "IVI",
            fingerprint = "geely/ivi/user", display = "Galaxy OS",
        ))
        assertNull(HeadUnitProfile.detect(
            manufacturer = "unknown", brand = "unknown", product = "KX11", model = "Monjaro",
            fingerprint = "unknown/kx11/user", display = "Android",
        ))
    }

    @Test fun `profile verifies but never fakes the centre screen viewport`() {
        assertTrue(GeelyXingyueLProfile.matchesViewport(1920, 720))
        assertFalse(GeelyXingyueLProfile.matchesViewport(1920, 719))
        assertFalse(GeelyXingyueLProfile.matchesViewport(3840, 720))
    }

    @Test fun `Geely car identity defaults do not depend on hardware profile detection`() {
        assertEquals("Geely", CarPlayVehicleBranding.DEFAULT_MANUFACTURER)
        assertEquals("Xingyue L", CarPlayVehicleBranding.DEFAULT_MODEL)
        assertEquals("GEELY", GeelyXingyueLProfile.CARPLAY_OEM_LABEL)
        assertEquals(R.drawable.ic_geely_auto_2023, CarPlayVehicleBranding.DEFAULT_ICON_RESOURCE)
    }

    @Test fun `vehicle adapter never identifies KX11 from screen or platform evidence alone`() {
        val platformOnly = GeelyVehicleAdapter.detect(GeelyVehicleEvidence(
            manufacturer = "Geely", brand = "Geely", product = "ivi", model = "unknown",
            fingerprint = "geely/ivi/user", display = "Galaxy OS", androidApi = 12,
        ))
        assertEquals(GeelyDetectionConfidence.POSSIBLE, platformOnly.confidence)
        assertNull(platformOnly.profile)

        val kx11 = GeelyVehicleAdapter.detect(GeelyVehicleEvidence(
            manufacturer = "ECARX", brand = "Geely", product = "KX11", model = "Xingyue L 2024 天际",
            fingerprint = "geely/kx11/user", display = "Galaxy OS", androidApi = 12,
        ))
        assertEquals(GeelyDetectionConfidence.IDENTIFIED, kx11.confidence)
        assertEquals(GeelyKx11Profile.KX11_2024_TIANJI, kx11.profile)
    }

    @Test fun `candidate labels identify manual selection without claiming compatibility`() {
        assertEquals("KX11 2024 天际版", GeelyVehicleAdapter.label(GeelyKx11Profile.KX11_2024_TIANJI))
        assertEquals("KX11 2024 Tianji A2 (candidate)",
            GeelyVehicleAdapter.label(GeelyKx11Profile.KX11_2024_TIANJI_A2))
        assertEquals("KX11 Generic", GeelyVehicleAdapter.label(GeelyKx11Profile.KX11_GENERIC))
    }

    @Test fun `explicit KX11 A2 identity is a candidate and does not infer OEM compatibility`() {
        val detection = GeelyVehicleAdapter.detect(GeelyVehicleEvidence(
            manufacturer = "ECARX", brand = "Geely", product = "KX11_A2", model = "Xingyue L",
            fingerprint = "geely/kx11_a2/user", display = "Galaxy OS", androidApi = 30,
        ))

        assertEquals(GeelyDetectionConfidence.IDENTIFIED, detection.confidence)
        assertEquals(GeelyKx11Profile.KX11_2024_TIANJI_A2, detection.profile)
        // The profile is identification metadata only; it enables no vehicle operation.
        assertTrue(detection.evidence.any { it.contains("KX11") })
    }
}
