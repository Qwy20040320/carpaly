package com.shilapi.xcertplay

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

    @Test fun `only the active Geely profile selects the Geely CarPlay icon`() {
        assertTrue(CarPlayVehicleBranding.usesGeelyIcon(HeadUnitProfile.GEELY_XINGYUE_L))
        assertFalse(CarPlayVehicleBranding.usesGeelyIcon(HeadUnitProfile.AUTOMATIC))
        assertFalse(CarPlayVehicleBranding.usesGeelyIcon(HeadUnitProfile.GENERIC))
        assertFalse(CarPlayVehicleBranding.usesGeelyIcon(null))
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
        assertEquals("KX11 Generic", GeelyVehicleAdapter.label(GeelyKx11Profile.KX11_GENERIC))
    }
}
