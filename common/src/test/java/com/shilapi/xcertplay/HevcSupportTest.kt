package com.shilapi.xcertplay

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HevcSupportTest {
    private val software = HevcSupport.Decoder("OMX.google.hevc.decoder", false)
    private val hardware = HevcSupport.Decoder("OMX.qcom.video.decoder.hevc", true)

    @Test fun softwareOnlyFallsBackByDefault() {
        assertFalse(HevcSupport.usable(true, false, listOf(software)))
        assertFalse(HevcSupport.usable(true, false, emptyList()))
    }

    @Test fun hardwareOrExplicitSoftwareChoiceKeepsHevc() {
        assertTrue(HevcSupport.usable(true, false, listOf(hardware)))
        assertTrue(HevcSupport.usable(true, true, listOf(software)))
        assertFalse(HevcSupport.usable(true, true, emptyList()))
    }

    @Test fun disabledSettingAlwaysUsesH264() {
        assertFalse(HevcSupport.usable(false, true, listOf(hardware)))
    }
}
